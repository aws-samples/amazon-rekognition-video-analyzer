# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
#     http://aws.amazon.com/asl/
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.

import sys
import pickle
import datetime
import cv2
import boto3
import time
from multiprocessing import Pool
import pytz

kinesis_client = boto3.client("kinesis")
rekog_client = boto3.client("rekognition")

camera_index = 0 # 0 is usually the built-in webcam
capture_rate = 30 # Frame capture rate.. every X frames. Positive integer.
rekog_max_labels = 123
rekog_min_conf = 50.0

#Send frame to Kinesis stream
def encode_and_send_frame(frame, frame_count, enable_kinesis=True, enable_rekog=False, write_file=False):
    try:
        #convert opencv Mat to jpg image
        #print "----FRAME---"
        retval, buff = cv2.imencode(".jpg", frame)

        img_bytes = bytearray(buff)

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

    argv_len = len(sys.argv)

    if argv_len > 1 and sys.argv[1].isdigit():
        capture_rate = int(sys.argv[1])

    cap = cv2.VideoCapture(0) #Use 0 for built-in camera. Use 1, 2, etc. for attached cameras.
    pool = Pool(processes=3)

    frame_count = 0
    while True:
        # Capture frame-by-frame
        ret, frame = cap.read()
        #cv2.resize(frame, (640, 360));

        if ret is False:
            break

        if frame_count % capture_rate == 0:
            result = pool.apply_async(encode_and_send_frame, (frame, frame_count, True, False, False,))

        frame_count += 1

        # Display the resulting frame
        cv2.imshow('frame', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # When everything done, release the capture
    cap.release()
    cv2.destroyAllWindows()
    return

if __name__ == '__main__':
    main()

