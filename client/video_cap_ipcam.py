# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
#     http://aws.amazon.com/asl/
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.

import urllib.request
import sys
import datetime
import base64
import boto3
import json
import pickle
import cv2
from multiprocessing import Pool
import numpy as np
import code
import time
import pytz


kinesis_client = boto3.client("kinesis")
rekog_client = boto3.client("rekognition")

#Frame capture parameters
default_capture_rate = 30 #frame capture rate.. every X frames. Positive integer.

#Rekognition paramters
rekog_max_labels = 123
rekog_min_conf = 50.0


#Send frame to Kinesis stream
def send_jpg(frame_jpg, frame_count, enable_kinesis=True, enable_rekog=False, write_file=False):
    try:

        img_bytes = frame_jpg

        utc_dt = pytz.utc.localize(datetime.datetime.now())
        now_ts_utc = (utc_dt - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds()


        frame_package = {
            'ApproximateCaptureTime' : now_ts_utc,
            'FrameCount' : frame_count,
            'ImageBytes' : img_bytes
        }

        if write_file:
            print("Writing file img_{}.jpg".format(frame_count))
            target = open("img_{}.jpg".format(frame_count), 'w')
            target.write(img_bytes)
            target.close()

        #put encoded image in kinesis stream
        if enable_kinesis:
            print("Sending image to Kinesis")
            response = kinesis_client.put_record(
                StreamName="FrameStream",
                Data=pickle.dumps(frame_package),
                PartitionKey="partitionkey"
            )
            print(response)

        if enable_rekog:
            response = rekog_client.detect_labels(
                Image={
                    'Bytes': img_bytes
                },
                MaxLabels=rekog_max_labels,
                MinConfidence=rekog_min_conf
            )
            print(response)

    except Exception as e:
        print(e)


def main():

    ip_cam_url = ''
    capture_rate = default_capture_rate
    argv_len = len(sys.argv)

    if argv_len > 1:
        ip_cam_url = sys.argv[1]
        
        if argv_len > 2 and sys.argv[2].isdigit():
            capture_rate = int(sys.argv[2])
    else:
        print("usage: video_cap_ipcam.py <ip-cam-url> [capture-rate]")
        return

    print("Capturing from '{}' at a rate of 1 every {} frames...".format(ip_cam_url, capture_rate))
    stream = urllib.request.urlopen(ip_cam_url)
    
    bytes = b''
    pool = Pool(processes=3)

    frame_count = 0
    while True:
        # Capture frame-by-frame
        frame_jpg = b''

        bytes += stream.read(16384*2)
        b = bytes.rfind(b'\xff\xd9')
        a = bytes.rfind(b'\xff\xd8', 0, b-1)


        if a != -1 and b != -1:
            #print 'Found JPEG markers. Start {}, End {}'.format(a,b)
            
            frame_jpg_bytes = bytes[a:b+2]
            bytes = bytes[b+2:]

            if frame_count % capture_rate == 0:
                
                #You can perform any image pre-processing here using OpenCV2.
                #Rotating image 90 degrees to the left:
                nparr = np.fromstring(frame_jpg_bytes, dtype=np.uint8)
                
                #Rotate 90 degrees counterclockwise
                img_cv2_mat = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                rotated_img = cv2.rotate(img_cv2_mat, cv2.ROTATE_90_COUNTERCLOCKWISE)
                
                retval, new_frame_jpg_bytes = cv2.imencode(".jpg", rotated_img)

                #Send to Kinesis
                result = pool.apply_async(send_jpg, (bytearray(new_frame_jpg_bytes), frame_count, True, False, False,))

            frame_count += 1

if __name__ == '__main__':
    main()
