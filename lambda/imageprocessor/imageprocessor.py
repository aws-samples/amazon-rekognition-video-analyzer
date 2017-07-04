# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
#     http://aws.amazon.com/asl/
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.

from __future__ import print_function
import base64
import datetime
import time
import decimal
import uuid
import json
import cPickle
import boto3
import pytz
from pytz import timezone


def load_config():
    '''Load configuration from file.'''
    with open('imageprocessor-params.json', 'r') as conf_file:
        conf_json = conf_file.read()
        return json.loads(conf_json)

def convert_ts(ts, config):
    '''Converts a timestamp to the configured timezone. Returns a localized datetime object.'''
    #lambda_tz = timezone('US/Pacific')
    tz = timezone(config['timezone'])
    utc = pytz.utc
    
    utc_dt = utc.localize(datetime.datetime.utcfromtimestamp(ts))

    localized_dt = utc_dt.astimezone(tz)

    return localized_dt


def process_image(event, context):

    #Initialize clients
    rekog_client = boto3.client('rekognition')
    sns_client = boto3.client('sns')
    s3_client = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')

    #Load config
    config = load_config()

    s3_bucket = config["s3_bucket"]
    s3_key_frames_root = config["s3_key_frames_root"]

    ddb_table = dynamodb.Table(config["ddb_table"])
      
    rekog_max_labels = config["rekog_max_labels"]
    rekog_min_conf = float(config["rekog_min_conf"])

    label_watch_list = config["label_watch_list"]
    label_watch_min_conf = float(config["label_watch_min_conf"])
    label_watch_phone_num = config["label_watch_phone_num"]

    #Iterate on frames fetched from Kinesis
    for record in event['Records']:

        frame_package_b64 = record['kinesis']['data']
        frame_package = cPickle.loads(base64.b64decode(frame_package_b64))

        img_bytes = frame_package["ImageBytes"]
        approx_capture_ts = frame_package["ApproximateCaptureTime"]
        frame_count = frame_package["FrameCount"]
        
        now_ts = time.time()

        frame_id = str(uuid.uuid4())
        processed_timestamp = decimal.Decimal(now_ts)
        approx_capture_timestamp = decimal.Decimal(approx_capture_ts)
        
        now = convert_ts(now_ts, config)
        year = now.strftime("%Y")
        mon = now.strftime("%m")
        day = now.strftime("%d")
        hour = now.strftime("%H")

        rekog_response = rekog_client.detect_labels(
            Image={
                'Bytes': img_bytes
            },
            MaxLabels=rekog_max_labels,
            MinConfidence=rekog_min_conf
        )


        #Iterate on rekognition labels...
        for label in rekog_response['Labels']:
            
            lbl = label['Name']
            conf = label['Confidence']
            label['OnWatchList'] = False

            #Print labels and confidence to lambda console
            print('{} .. conf %{:.2f}'.format(lbl, conf))

            #Check label watch list and trigger action
            if(label_watch_phone_num 
                and lbl.upper() in 
                    (label.upper() for label in label_watch_list) 
                and conf >= label_watch_min_conf):
                
                label['OnWatchList'] = True

                notification_txt = 'On {}, {} was detected with %{} confidence.'.format(
                    now.strftime('%x %X %Z'), 
                    lbl, 
                    round(conf,2))

                print(notification_txt)

                #Send SNS notification
                sns_client.publish(PhoneNumber=label_watch_phone_num, Message=notification_txt)
            
            #Convert from float to decimal for DynamoDB
            label['Confidence'] = decimal.Decimal(conf)

        #print("rekog_response:\n{}", rekog_response)
        s3_key = (s3_key_frames_root + '{}/{}/{}/{}/{}.jpg').format(year, mon, day, hour, frame_id)
        
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=img_bytes
        )
        
        #Persist frame data in dynamodb

        item = {
            'frame_id': frame_id,
            'processed_timestamp' : processed_timestamp,
            'approx_capture_timestamp' : approx_capture_timestamp,
            'rekog_labels' : rekog_response['Labels'],
            'rekog_orientation_correction' : 
                rekog_response['OrientationCorrection'] 
                if 'OrientationCorrection' in rekog_response else 'ROTATE_0',
            'processed_year_month' : year + mon, #To be used as a Hash Key for DynamoDB GSI
            's3_bucket' : s3_bucket,
            's3_key' : s3_key
        }

        ddb_table.put_item(Item=item)

    print('Successfully processed {} records.'.format(len(event['Records'])))
    return

def handler(event, context):
    return process_image(event, context)
