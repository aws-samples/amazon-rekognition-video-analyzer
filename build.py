# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
#     http://aws.amazon.com/asl/
# or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.
import os
import shutil
import zipfile
import time
from pynt import task
import boto3
import botocore
from botocore.exceptions import ClientError
import json
from subprocess import call
import http.server
import socketserver

def write_dir_to_zip(src, zf):
    '''Write a directory tree to an open ZipFile object.'''
    abs_src = os.path.abspath(src)
    for dirname, subdirs, files in os.walk(src):
        for filename in files:
            absname = os.path.abspath(os.path.join(dirname, filename))
            arcname = absname[len(abs_src) + 1:]
            print('zipping %s as %s' % (os.path.join(dirname, filename),
                                        arcname))
            zf.write(absname, arcname)

def read_json(jsonf_path):
    '''Read a JSON file into a dict.'''
    with open(jsonf_path, 'r') as jsonf:
        json_text = jsonf.read()
        return json.loads(json_text)

def check_bucket_exists(bucketname):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucketname)
    exists = True
    try:
        s3.meta.client.head_bucket(Bucket=bucketname)
    except botocore.exceptions.ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            exists = False
    return exists

@task()
def clean():
    '''Clean build directory.'''
    print('Cleaning build directory...')

    if os.path.exists('build'):
    	shutil.rmtree('build')
    
    os.mkdir('build')

@task()
def packagelambda(* functions):
    '''Package lambda functions into a deployment-ready zip files.''' 
    if not os.path.exists('build'):
        os.mkdir('build')

    os.chdir("build")

    if(len(functions) == 0):
        functions = ("framefetcher", "imageprocessor")

    for function in functions:
        print('Packaging "%s" lambda function in directory' % function)
        zipf = zipfile.ZipFile("%s.zip" % function, "w", zipfile.ZIP_DEFLATED)
        
        write_dir_to_zip("../lambda/%s/" % function, zipf)
        zipf.write("../config/%s-params.json" % function, "%s-params.json" % function)

        zipf.close()

    os.chdir("..")
    
    return


@task()
def updatelambda(*functions):
    '''Directly update lambda function code in AWS (without upload to S3).'''
    lambda_client = boto3.client('lambda')

    if(len(functions) == 0):
        functions = ("framefetcher", "imageprocessor")

    for function in functions:
        with open('build/%s.zip' % (function), 'rb') as zipf:
            lambda_client.update_function_code(
                FunctionName=function,
                ZipFile=zipf.read()
            )
    return

@task()
def deploylambda(* functions, **kwargs):
    '''Upload lambda functions .zip file to S3 for download by CloudFormation stack during creation.'''
    
    cfn_params_path = kwargs.get("cfn_params_path", "config/cfn-params.json")

    if(len(functions) == 0):
        functions = ("framefetcher", "imageprocessor")

    region_name = boto3.session.Session().region_name
    s3_keys = {}

    cfn_params_dict = read_json(cfn_params_path)
    src_s3_bucket_name = cfn_params_dict["SourceS3BucketParameter"]
    s3_keys["framefetcher"] = cfn_params_dict["FrameFetcherSourceS3KeyParameter"]
    s3_keys["imageprocessor"] = cfn_params_dict["ImageProcessorSourceS3KeyParameter"]

    s3_client = boto3.client("s3")
    
    print("Checking if S3 Bucket '%s' exists..." % (src_s3_bucket_name))

    if( not check_bucket_exists(src_s3_bucket_name)):
        print("Bucket %s not found. Creating in region %s." % (src_s3_bucket_name, region_name))

        if( region_name == "us-east-1"):
            s3_client.create_bucket(
                # ACL="authenticated-read",
                Bucket=src_s3_bucket_name
            )
        else:
            s3_client.create_bucket(
                #ACL="authenticated-read",
                Bucket=src_s3_bucket_name,
                CreateBucketConfiguration={
                    "LocationConstraint": region_name
                }
            )

    for function in functions:
        
        print("Uploading function '%s' to '%s'" % (function, s3_keys[function]))
        
        with open('build/%s.zip' % (function), 'rb') as data:
            s3_client.upload_fileobj(data, src_s3_bucket_name, s3_keys[function])
    
    return

@task()
def createstack(**kwargs):
    '''Create the Amazon Rekognition Video Analyzer stack using CloudFormation.'''

    cfn_path = kwargs.get("cfn_path", "aws-infra/aws-infra-cfn.yaml") 
    global_params_path = kwargs.get("global_params_path", "config/global-params.json") 
    cfn_params_path = kwargs.get("cfn_params_path", "config/cfn-params.json")

    global_params_dict = read_json(global_params_path)
    stack_name = global_params_dict["StackName"]

    cfn_params_dict = read_json(cfn_params_path)
    cfn_params = []
    for key, value in cfn_params_dict.items():
        cfn_params.append({
            'ParameterKey' : key,
            'ParameterValue' : value
            })

    cfn_file = open(cfn_path, 'r')
    cfn_template = cfn_file.read(51200) #Maximum size of a cfn template

    cfn_client = boto3.client('cloudformation')

    print("Attempting to CREATE '%s' stack using CloudFormation." % (stack_name))
    start_t = time.time()
    response = cfn_client.create_stack(
        StackName=stack_name,
        TemplateBody=cfn_template,
        Parameters=cfn_params,
        Capabilities=[
        	'CAPABILITY_NAMED_IAM',
        ],
    )

    print("Waiting until '%s' stack status is CREATE_COMPLETE" % stack_name)
    cfn_stack_delete_waiter = cfn_client.get_waiter('stack_create_complete')
    cfn_stack_delete_waiter.wait(StackName=stack_name)

    print("Stack CREATED in approximately %d secs." % int(time.time() - start_t))

@task()
def updatestack(**kwargs):
    '''Update the Amazon Rekognition Video Analyzer CloudFormation stack.'''
    cfn_path = kwargs.get("cfn_path", "aws-infra/aws-infra-cfn.yaml") 
    global_params_path = kwargs.get("global_params_path", "config/global-params.json") 
    cfn_params_path = kwargs.get("cfn_params_path", "config/cfn-params.json")

    global_params_dict = read_json(global_params_path)
    stack_name = global_params_dict["StackName"]

    cfn_params_dict = read_json(cfn_params_path)
    cfn_params = []
    for key, value in cfn_params_dict.items():
        cfn_params.append({
            'ParameterKey' : key,
            'ParameterValue' : value
            })

    cfn_file = open(cfn_path, 'r')
    cfn_template = cfn_file.read(51200) #Maximum size of a cfn template

    cfn_client = boto3.client('cloudformation')

    print("Attempting to UPDATE '%s' stack using CloudFormation." % (stack_name))
    try:
        start_t = time.time()
        response = cfn_client.update_stack(
            StackName=stack_name,
            TemplateBody=cfn_template,
            Parameters=cfn_params,
            Capabilities=[
                'CAPABILITY_NAMED_IAM',
            ],
        )

        print("Waiting until '%s' stack status is UPDATE_COMPLETE" % stack_name)
        cfn_stack_update_waiter = cfn_client.get_waiter('stack_update_complete')
        cfn_stack_update_waiter.wait(StackName=stack_name)

        print("Stack UPDATED in approximately %d secs." % int(time.time() - start_t))
    except ClientError as e:
        print("EXCEPTION: " + e.response["Error"]["Message"])


@task()
def stackstatus(global_params_path="config/global-params.json"):
    '''Check the status of the Amazon Rekognition Video Analyzer CloudFormation stack.'''
    global_params_dict = read_json(global_params_path)
    stack_name = global_params_dict["StackName"]

    cfn_client = boto3.client('cloudformation')

    try:
        response = cfn_client.describe_stacks(
            StackName=stack_name
        )

        if(response["Stacks"][0]):
            print("Stack '%s' has the status '%s'" % (stack_name, response["Stacks"][0]["StackStatus"]))
    
    except ClientError as e:
        print("EXCEPTION: " + e.response["Error"]["Message"])


@task()
def deletestack(** kwargs):
    '''Delete Amazon Rekognition Video Analyzer infrastructure using CloudFormation.'''

    cfn_path = kwargs.get("cfn_path", "aws-infra/aws-infra-cfn.yaml") 
    global_params_path = kwargs.get("global_params_path", "config/global-params.json") 
    cfn_params_path = kwargs.get("cfn_params_path", "config/cfn-params.json")

    global_params_dict = read_json(global_params_path)
    cfn_params_dict = read_json(cfn_params_path)

    stack_name = global_params_dict["StackName"]
    usage_plan_name = cfn_params_dict["ApiGatewayUsagePlanNameParameter"]
    
    cfn_client = boto3.client('cloudformation')
    apigw_client = boto3.client('apigateway')

    # Empty all objects in the frame bucket prior to deleting the stack.
    frame_s3_bucket_name = cfn_params_dict["FrameS3BucketNameParameter"]
    print("Attempting to DELETE ALL OBJECTS in '%s' bucket." % frame_s3_bucket_name)
    
    s3 = boto3.resource('s3')
    s3.Bucket(frame_s3_bucket_name).objects.delete()

    print("Attempting to DELETE '%s' stack using CloudFormation." % stack_name)
    start_t = time.time()
    response = cfn_client.delete_stack(
        StackName=stack_name
    )

    print("Waiting until '%s' stack status is DELETE_COMPLETE" % stack_name)
    cfn_stack_delete_waiter = cfn_client.get_waiter('stack_delete_complete')
    cfn_stack_delete_waiter.wait(StackName=stack_name)
    print("Stack DELETED in approximately %d secs." % int(time.time() - start_t))

    print("Cleaning up API Gateway UsagePlan resource.")
    usage_plans = apigw_client.get_usage_plans()
    for usage_plan in usage_plans['items']:
        if(usage_plan['name'] == usage_plan_name):
            apigw_client.delete_usage_plan(usagePlanId=usage_plan['id'])



@task()
def webui(webdir="web-ui/", global_params_path="config/global-params.json", cfn_params_path="config/cfn-params.json"):
    '''Build the Amazon Rekognition Video Analyzer Web UI.'''

    # Clean web-ui build directory
    if not os.path.exists('build'):
        os.mkdir('build')

    web_build_dir = 'build/%s' % webdir

    if os.path.exists(web_build_dir):
        shutil.rmtree(web_build_dir)

    # Copy web-ui source
    print("Copying Web UI source from '%s' to build directory." % webdir)
    shutil.copytree(webdir, web_build_dir)

    global_params_dict = read_json(global_params_path)
    stack_name = global_params_dict["StackName"]

    cfn_params_dict = read_json(cfn_params_path)

    cfn_client = boto3.client('cloudformation')
    apigw_client = boto3.client('apigateway')


    # Get Rest API Id
    print("Retrieving API key from stack '%s'." % stack_name)
    response = cfn_client.describe_stack_resource(
        StackName=stack_name,
        LogicalResourceId=cfn_params_dict["ApiGatewayRestApiNameParameter"]
    )

    rest_api_id = response["StackResourceDetail"]["PhysicalResourceId"]

    # Get API Key
    response = cfn_client.describe_stack_resource(
        StackName=stack_name,
        LogicalResourceId="VidAnalyzerApiKey"
    )

    api_key_id = response["StackResourceDetail"]["PhysicalResourceId"]

    response = apigw_client.get_api_key(
        apiKey=api_key_id,
        includeValue=True
    )

    api_key_value = response["value"]

    api_stage_name = cfn_params_dict["ApiGatewayStageNameParameter"]

    region_name = boto3.session.Session().region_name

    print("Putting together the API Gateway base URL.")
    
    api_base_url = "https://%s.execute-api.%s.amazonaws.com/%s" % (rest_api_id, region_name, api_stage_name)

    print("Writing API key and API base URL to apigw.js in '%ssrc/'" % web_build_dir)

    # Output key value and invoke url to apigw.js
    apigw_js = open('%ssrc/apigw.js' % web_build_dir, 'w')
    apigw_js.write('var apiBaseUrl="%s";\nvar apiKey="%s";\n' % (api_base_url, api_key_value))
    apigw_js.close()



@task()
def webuiserver(webdir="web-ui/",port=8080):
    '''Start a local lightweight HTTP server to serve the Web UI.'''
    web_build_dir = 'build/%s' % webdir

    os.chdir(web_build_dir)
    
    Handler = http.server.SimpleHTTPRequestHandler

    httpd = socketserver.TCPServer(("0.0.0.0", port), Handler)

    print("Starting local Web UI Server in directory '%s' on port %s" % (web_build_dir, port))
    
    httpd.serve_forever()
    
    return

@task()
def videocaptureip(videouri, capturerate="30", clientdir="client"):
    '''Run the IP camera video capture client using parameters video URI and frame capture rate.'''
    os.chdir(clientdir)
    
    call(["python", "video_cap_ipcam.py", videouri, capturerate])

    os.chdir("..")

    return

@task()
def videocapture(capturerate="30",clientdir="client"):
    '''Run the video capture client with built-in camera. Default capture rate is 1 every 30 frames.'''
    os.chdir(clientdir)
    
    call(["python", "video_cap.py", capturerate])

    os.chdir("..")

    return

@task()
def deletedata(global_params_path="config/global-params.json", cfn_params_path="config/cfn-params.json", image_processor_params_path="config/imageprocessor-params.json"):
    '''DELETE ALL collected frames and metadata in Amazon S3 and Amazon DynamoDB. Use with caution!'''
    
    cfn_params_dict = read_json(cfn_params_path)
    img_processor_params_dict = read_json(image_processor_params_path)

    frame_s3_bucket_name = cfn_params_dict["FrameS3BucketNameParameter"]
    frame_ddb_table_name = img_processor_params_dict["ddb_table"]

    proceed = input("This command will DELETE ALL DATA in S3 bucket '%s' and DynamoDB table '%s'.\nDo you wish to continue? [Y/N] " \
        % (frame_s3_bucket_name, frame_ddb_table_name))

    if(proceed.lower() != 'y'):
        print("Aborting deletion.")
        return


    print("Attempting to DELETE ALL OBJECTS in '%s' S3 bucket." % frame_s3_bucket_name)
    
    s3 = boto3.resource('s3')
    s3.Bucket(frame_s3_bucket_name).objects.delete()

    print("Attempting to DELETE ALL ITEMS in '%s' DynamoDB table." % frame_ddb_table_name)
    dynamodb = boto3.client('dynamodb')
    ddb_table = boto3.resource('dynamodb').Table(frame_ddb_table_name)

    last_eval_key = None
    keep_scanning = True
    batch_count = 0
    while keep_scanning:
        batch_count += 1

        if(keep_scanning and last_eval_key):
            response = dynamodb.scan(
                TableName=frame_ddb_table_name,
                Select='SPECIFIC_ATTRIBUTES',
                AttributesToGet=[
                    'frame_id',
                ],
                ExclusiveStartKey=last_eval_key
            )
        else:
            response = dynamodb.scan(
                TableName=frame_ddb_table_name,
                Select='SPECIFIC_ATTRIBUTES',
                AttributesToGet=[
                    'frame_id',
                ]
            )

        last_eval_key = response.get('LastEvaluatedKey', None)
        keep_scanning = True if last_eval_key else False

        with ddb_table.batch_writer() as batch:
            for item in response["Items"]:
                print("Deleting Item with 'frame_id': %s" % item['frame_id']['S'])
                batch.delete_item(
                    Key={
                        'frame_id': item['frame_id']['S']
                    }
                )
    print("Deleted %s batches of items from DynamoDB." % batch_count)

    return

