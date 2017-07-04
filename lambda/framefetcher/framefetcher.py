# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
#     http://aws.amazon.com/asl/
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.

from __future__ import print_function

import boto3
from boto3.dynamodb.conditions import Key, Attr
import datetime
import time
import json
import decimal
from datetime import timedelta


class DecimalEncoder(json.JSONEncoder):
    def default(self, o): # pylint: disable=E0202
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

def load_config():

    with open('framefetcher-params.json', 'r') as conf_file:
        conf_json = conf_file.read()
        return json.loads(conf_json)

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res, cls=DecimalEncoder),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': "*"
        },
    }


def fetch_frames(event, context):

    #Initialize clients
    dynamodb = boto3.resource('dynamodb')
    s3_client = boto3.client('s3')
    
    #Load config
    config = load_config()

    ddb_table = dynamodb.Table(config['ddb_table'])
    ddb_gsi_name = config['ddb_gsi_name']
    fetch_horizon_hrs = float(config['fetch_horizon_hrs'])
    fetch_limit = config['fetch_limit']

    #Process "GET" request
    if event['httpMethod'] == "GET":
        now = datetime.datetime.now()
        year = now.strftime("%Y")
        mon = now.strftime("%m")

        ts_at_fetch_horizon = time.time() - (fetch_horizon_hrs * 60 * 60)

        ddb_resp = ddb_table.query(
            IndexName=ddb_gsi_name,
            
            KeyConditionExpression=Key('processed_year_month').eq(year + mon) 
            & Key('processed_timestamp').gt(decimal.Decimal(ts_at_fetch_horizon)),
            Limit=fetch_limit,
            ScanIndexForward=False #Sort descendingly -- show most recent captured frames first.
        )

        for item in ddb_resp["Items"]:

            s3_key = item["s3_key"]
            s3_bucket = item["s3_bucket"]
            # Note the following. 
            # (1) even if the url expires in days or weeks, the presigned 
            # url is usable only if the temporary IAM credentials that generated 
            # it haven't expired. These are the credentials assumed by this lambda function.
            # (2) Your bucket policy needs to allow "read" access to "authenticated AWS users"
            # (3) Ensure this Lambda function's role has S3FullAccess policy attached to it. 
            s3_presigned_url_expiry = config["s3_pre_signed_url_expiry"]

            s3_presigned_url = s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket' : s3_bucket,
                    'Key' : s3_key
                },
                ExpiresIn=s3_presigned_url_expiry
            )

            item['s3_presigned_url'] = s3_presigned_url
        
        print (ddb_resp)

        return respond(None, ddb_resp["Items"])

def handler(event, context):
    return fetch_frames(event, context)
    
