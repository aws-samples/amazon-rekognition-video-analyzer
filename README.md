Create a Serverless Pipeline for Video Frame Analysis and Alerting
========

## Introduction
Imagine being able to capture live video streams, identify objects using deep learning, and then trigger actions or notifications based on the identified objects -- all with low latency and without a single server to manage.

This is exactly what this project is going to help you accomplish with AWS. You will be able to setup and run a live video capture, analysis, and alerting solution prototype.

The prototype was conceived to address a specific use case, which is alerting based on a live video feed from an IP security camera. At a high level, the solution works as follows. A camera surveils a particular area, streaming video over the network to a video capture client. The client samples video frames and sends them over to AWS, where they are analyzed and stored along with metadata. If certain objects are detected in the analyzed video frames, SMS alerts are sent out. Once a person receives an SMS alert, they will likely want to know what caused it. For that, sampled video frames can be monitored with low latency using a web-based user interface.

Here's the prototype's conceptual architecture:

![Architecture](https://moanany-share.s3.amazonaws.com/serverless_pipeline_arch_2.png?AWSAccessKeyId=AKIAJZICANBOQ5ADZ7YQ&Expires=1532717705&Signature=z1MT0CWAPhDjc9YI5wx25WqlVLQ%3D)

Let's go through the steps necessary to get this prototype up and running. If you are starting from scratch and are not familiar with Python, completing all steps can take a few hours.

## Preparing your development environment
Here’s a high-level checklist of what you need to do to setup your development environment.

1. Sign up for an AWS account if you haven't already and create an Administrator User. The steps are published [here](http://docs.aws.amazon.com/lambda/latest/dg/setting-up.html).

2. Ensure that you have Python 2.7+ and Pip on your machine. Instructions for that varies based on your operating system and OS version.

3. Create a Python [virtual environment](https://virtualenv.pypa.io/en/stable/) for the project with Virtualenv. This helps keep project’s python dependencies neatly isolated from your Operating System’s default python installation. **Once you’ve created a virtual python environment, activate it before moving on with the following steps**.

4. Use Pip to [install AWS CLI](http://docs.aws.amazon.com/cli/latest/userguide/installing.html). [Configure](http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html) the AWS CLI. It is recommended that the access keys you configure are associated with an IAM User who has full access to the following:
 - Amazon S3
 - Amazon DynamoDB
 - Amazon Kinesis
 - AWS Lambda
 - Amazon CloudWatch and CloudWatch Logs
 - AWS CloudFormation
 - Amazon Rekognition
 - Amazon SNS
 - Amazon API Gateway
 - Creating IAM Roles

 The IAM User can be the Administrator User you created in Step 1.

5. Make sure you choose a region where all of the above services are available. Regions us-east-1 (N. Virginia), us-west-2 (Oregon), and eu-west-1 (Ireland) fulfill this criterion. Visit [this page](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/) to learn more about service availability in AWS regions.

6. Use Pip to install [Open CV](https://github.com/opencv/opencv) 3 python dependencies and then compile, build, and install Open CV 3 (required by Video Cap clients). You can follow [this guide](http://www.pyimagesearch.com/2016/11/28/macos-install-opencv-3-and-python-2-7/) to get Open CV 3 up and running on OS X Sierra with Python 2.7. There's [another guide](http://www.pyimagesearch.com/2016/12/05/macos-install-opencv-3-and-python-3-5/) for Open CV 3 and Python 3.5 on OS X Sierra. Other guides exist as well for Windows and Raspberry Pi.

6. Use Pip to install [Boto3](http://boto3.readthedocs.io/en/latest/). Boto is the Amazon Web Services (AWS) SDK for Python, which allows Python developers to write software that makes use of Amazon services like S3 and EC2. Boto provides an easy to use, object-oriented API as well as low-level direct access to AWS services.

7. Use Pip to install [Pynt](https://github.com/rags/pynt). Pynt enables you to write project build scripts in Python.

8. Clone this GitHub repository. Choose a directory path for your project that does not contain spaces (I'll refer to the full path to this directory as _\<path-to-project-dir\>_).

9. Use Pip to install [pytz](http://pytz.sourceforge.net/). Pytz is needed for timezone calculations. Use the following commands:

```bash
pip install pytz # Install pytz in your virtual python env

pip install pytz -t <path-to-project-dir>/lambda/imageprocessor/ # Install pytz to be packaged and deployed with the Image Processor lambda function
```

Finally, obtain an IP camera. If you don’t have an IP camera, you can use your smartphone with an IP camera app. This is useful in case you want to test things out before investing in an IP camera. Also, you can simply use your laptop’s built-in camera or a connected USB camera. If you use an IP camera, make sure your camera is connected to the same Local Area Network as the Video Capture client.

## Configuring the project

In this section, I list every configuration file, parameters within it, and parameter default values. The build commands detailed later extract the majority of their parameters from these configuration files. Also, the prototype's two AWS Lambda functions - Image Processor and Frame Fetcher - extract parameters at runtime from `imageprocessor-params.json` and `framefetcher-params.json` respectively.

>**NOTE: Do not remove any of the attributes already specified in these files.**



> **NOTE: You must set the value of any parameter that has the tag NO-DEFAULT** 

### config/global-params.json

Specifies “global” build configuration parameters. It is read by multiple build scripts.

```json
{
    "StackName" : "video-analyzer-stack"
}
```
Parameters:

* `StackName` - The name of the stack to be created in your AWS account.

### config/cfn-params.json
Specifies and overrides default values of AWS CloudFormation parameters defined in the template (located at aws-infra/aws-infra-cfn.yaml). This file is read by a number of build scripts, including ```createstack```, ```deploylambda```, and ```webui```.

```json
{
    "SourceS3BucketParameter" : "<NO-DEFAULT>",
    "ImageProcessorSourceS3KeyParameter" : "src/lambda_imageprocessor.zip",
    "FrameFetcherSourceS3KeyParameter" : "src/lambda_framefetcher.zip",

    "FrameS3BucketNameParameter" : "<NO-DEFAULT>",

    "FrameFetcherApiResourcePathPart" : "enrichedframe",
    "ApiGatewayRestApiNameParameter" : "VidAnalyzerRestApi",
    "ApiGatewayStageNameParameter": "development",
    "ApiGatewayUsagePlanNameParameter" : "development-plan"
}
```
Parameters:

* `SourceS3BucketParameter` - The Amazon S3 bucket to which your AWS Lambda function packages (.zip files) will be dpeloyed. If a bucket with such a name does not exist, the `deploylambda` build command will create it for you with appropriate permissions. AWS CloudFormation will access this bucket to retrieve the .zip files for Image Processor and Frame Fetcher AWS Lambda functions.

* `ImageProcessorSourceS3KeyParameter` - The Amazon S3 key under which the Image Processor function .zip file will be stored.

* `FrameFetcherSourceS3KeyParameter` - The Amazon S3 key under which the Frame Fetcher function .zip file will be stored.

* `FrameS3BucketNameParameter` - The Amazon S3 bucket that will be used for storing video frame images.

* `FrameFetcherApiResourcePathPart` - The name of the Frame Fetcher API resource path part in the API Gateway URL.

* `ApiGatewayRestApiNameParameter` - The name of the API Gateway REST API to be created by AWS CloudFormation.

* `ApiGatewayStageNameParameter` - The name of the API Gateway stage to be created by AWS CloudFormation.

* `ApiGatewayUsagePlanNameParameter` - The name of the API Gateway usage plan to be created by AWS CloudFormation.


### config/imageprocessor-params.json
Specifies configuration parameters to be used at run-time by the Image Processor lambda function. This file is packaged along with the Image Processor lambda function code in a single .zip file using the `packagelambda` build script.

```json
{
	"s3_bucket" : "<NO-DEFAULT>",
	"s3_key_frames_root" : "frames/",

	"ddb_table" : "EnrichedFrame",

	"rekog_max_labels" : 123,
    "rekog_min_conf" : 50.0,

	"label_watch_list" : ["Human", "Pet", "Bag", "Toy"],
	"label_watch_min_conf" : 90.0,
	"label_watch_phone_num" : "",
	"timezone" : "US/Eastern"
}
```

* `s3_bucket` - The Amazon S3 bucket in which Image Processor will store captured video frame images. The value specified here _must_ match the value specified for the `FrameS3BucketNameParameter` parameter in the `cfn-params.json` file.

* `s3_key_frames_root` - The Amazon S3 key prefix that will be prepended to the keys of all stored video frame images.

* `ddb_table` - The Amazon DynamoDB table in which Image Processor will store video frame metadata. The default value,`EnrichedFrame`, matches the default value of the AWS CloudFormation template parameter `DDBTableNameParameter` in the `aws-infra/aws-infra-cfn.yaml` template file.

* `rekog_max_labels` - The maximum number of labels that Amazon Rekognition can return to Image Processor.

* `rekog_min_conf` - The minimum confidence required for a label identified by Amazon Rekognition. Any labels with confidence below this value will not be returned to Image Processor.

* `label_watch_list` - A list of labels for to watch out for. If any of the labels specified in this parameter are returned by Amazon Rekognition, an SMS alert will be sent via Amazon SNS. The label's confidence must exceed `label_watch_min_conf`.

* `label_watch_min_conf` - The minimum confidence required for a label to trigger a Watch List alert.

* `label_watch_phone_num` - The mobile phone number to which a Watch List SMS alert will be sent. Does not have a default value. **You must configure a valid phone number adhering to the E.164 format (e.g. +1404XXXYYYY) for the Watch List feature to become active.**

* `timezone` - The timezone used to report time and date in SMS alerts. By default, it is "US/Eastern". See this list of [country codes, names, continents, capitals, and pytz timezones](https://gist.github.com/pamelafox/986163)).

### config/framefetcher-params.json
Specifies configuration parameters to be used at run-time by the Frame Fetcher lambda function. This file is packaged along with the Frame Fetcher lambda function code in a single .zip file using the ```packagelambda``` build script.

```json
{
    "s3_pre_signed_url_expiry" : 1800,

    "ddb_table" : "EnrichedFrame",
    "ddb_gsi_name" : "processed_year_month-processed_timestamp-index",

    "fetch_horizon_hrs" : 24,
    "fetch_limit" : 3
}
```

* `s3_pre_signed_url_expiry` - Frame Fetcher returns video frame metadata. Along with the returned metadata, Frame Fetcher generates and returns a pre-signed URL for every video frame. Using a pre-signed URL, a client (such as the Web UI) can securely access the JPEG image associated with a particular frame. By default, the pre-signed URLs expire in 30 minutes.

* `ddb_table` - The Amazon DynamoDB table from which Frame Fetcher will fetch video frame metadata. The default value,`EnrichedFrame`, matches the default value of the AWS CloudFormation template parameter `DDBTableNameParameter` in the `aws-infra/aws-infra-cfn.yaml` template file.

* `ddb_gsi_name` - The name of the Amazon DynamoDB Global Secondary Index that Frame Fetcher will use to query frame metadata. The default value matches the default value of the AWS CloudFormation template parameter `DDBGlobalSecondaryIndexNameParameter` in the `aws-infra/aws-infra-cfn.yaml` template file.

* `fetch_horizon_hrs` - Frame Fetcher will exclude any video frames that were ingested prior to the point in the past represented by (time now - `fetch_horizon_hrs`).

* `fetch_limit` - The maximum number of video frame metadata items that Frame Fetcher will retrieve from Amazon DynamoDB.

## Building the prototype
Common interactions with the project have been simplified for you. Using pynt, the following tasks are automated with simple commands: 

- Creating, deleting, and updating the AWS infrastructure stack with AWS CloudFormation
- Packaging lambda code into .zip files and deploying them into an Amazon S3 bucket
- Running the video capture client to stream from a built-in laptop webcam or a USB camera
- Running the video capture client to stream from an IP camera (MJPEG stream)
- Build a simple web user interface (Web UI)
- Run a lightweight local HTTP server to serve Web UI for development and demo purposes

For a list of all available tasks, enter the following command in the root directory of this project:

```bash
pynt -l
```

The output represents the list of build commands available to you:

![pynt -l output](https://moanany-share.s3.amazonaws.com/pynt%20dash%20l.png?AWSAccessKeyId=AKIAJZICANBOQ5ADZ7YQ&Expires=1530338841&Signature=m6xRFWAs9v9DNmmWHIL4hD12ySk%3D)

Build commands are implemented as python scripts in the file ```build.py```. The scripts use the AWS Python SDK (Boto) under the hood. They are documented in the following section.

>Prior to using these build commands, you must configure the project. Configuration parameters are split across JSON-formatted files located under the config/ directory. Configuration parameters are described in detail in an earlier section.


## Build commands

This section describes important build commands and how to use them. If you want to use these commands right away to build the prototype, you may skip to the section titled _"Deploy and run the prototype"_.

### The `packagelambda` build command

Run this command to package the prototype's AWS Lambda functions and their dependencies (Image Processor and Frame Fetcher) into separate .zip packages (one per function). The deployment packages are created under the `build/` directory.

```bash
pynt packagelambda # Package both functions and their dependencies into zip files.

pynt packagelambda[framefetcher] # Package only Frame Fetcher.
```

Currently, only Image Processor requires an external dependency, [pytz](http://pytz.sourceforge.net/). If you add features to Image Processor or Frame Fetcher that require external dependencies, you should install the dependencies using Pip by issuing the following command.

```bash
pip install <module-name> -t <path-to-project-dir>/lambda/<lambda-function-dir>
```
For example, let's say you want to perform image processing in the Image Processor Lambda function. You may decide on using the [Pillow](http://pillow.readthedocs.io/en/3.0.x/index.html) image processing library. To ensure Pillow is packaged with your Lambda function in one .zip file, issue the following command:

```bash
pip install Pillow -t <path-to-project-dir>/lambda/imageprocessor #Install Pillow dependency
```

You can find more details on installing AWS Lambda dependencies [here](http://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html).

### The `deploylambda` build command

Run this command before you run `createstack`. The ```deploylambda``` command uploads Image Processor and Frame Fetcher .zip packages to Amazon S3 for pickup by AWS CloudFormation while creating the prototype's stack. This command will parse the deployment Amazon S3 bucket name and keys names from the cfn-params.json file. If the bucket does not exist, the script will create it. This bucket must be in the same AWS region as the AWS CloudFormation stack, or else the stack creation will fail. Without parameters, the command will deploy the .zip packages of both Image Processor and Frame Fetcher. You can specify either “imageprocessor” or “framefetcher” as a parameter between square brackets to deploy an individual function.

Here are sample command invocations.

```bash
pynt deploylambda # Deploy both functions to Amazon S3.

pynt deploylambda[framefetcher] # Deploy only Frame Fetcher to Amazon S3.
```

### The `createstack` build command
The createstack command creates the prototype's AWS CloudFormation stack behind the scenes by invoking the `create_stack()` API. The AWS CloudFormation template used is located at aws-infra/aws-infra-cfn.yaml under the project’s root directory. The prototype's stack requires a number of parameters to be successfully created. The createstack script reads parameters from both global-params.json and cfn-params.json configuration files. The script then passes those parameters to the `create_stack()` call.

Note that you must, first, package and deploy Image Processor and Frame Fetcher functions to Amazon S3 using the `packagelambda` and `deploylambda` commands (documented later in this guid) for the AWS CloudFormation stack creation to succeed.

You can issue the command as follows:

```bash
pynt createstack
```

Stack creation should take only a couple of minutes. At any time, you can check on the prototype's stack status either through the AWS CloudFormation console or by issuing the following command.

```bash
pynt stackstatus
```

Congratulations! You’ve just created the prototype's entire architecture in your AWS account.


### The `deletestack` build command

The `deletestack` command, once issued, does a few things. 
First, it empties the Amazon S3 bucket used to store video frame images. Next, it calls the AWS CloudFormation delete_stack() API to delete the prototype's stack from your account. Finally, it removes any unneeded resources not deleted by the stack (for example, the prototype's API Gateway Usage Plan resource).

You can issue the `deletestack` command as follows.

```bash
pynt deletestack
```

As with `createstack`, you can monitor the progress of stack deletion using the `stackstatus` build command.

### The `deletedata` build command

The `deletedata` command, once issued, empties the Amazon S3 bucket used to store video frame images. Next, it also deletes all items in the DynamoDB table used to store frame metadata.

Use this command to clear all previously ingested video frames and associated metadata. The command will ask for confirmation [Y/N] before proceeding with deletion.

You can issue the `deletedata` command as follows.

```bash
pynt deletedata
```

As with `createstack`, you can monitor the progress of stack deletion using the `stackstatus` build command.

### The `stackstatus` build command

The `stackstatus` command will query AWS CloudFormation for the status of the prototype's stack. This command is most useful for quickly checking that the prototype is up and running (i.e. status is "CREATE\_COMPLETE" or "UPDATE\_COMPLETE") and ready to serve requests from the Web UI.

You can issue the command as follows.


```bash
pynt stackstatus # Get the prototype's Stack Status
```


### The `webui` build command

Run this command when the prototype's stack has been created (using `createstack`). The webui command “builds” the Web UI through which you can monitor incoming captured video frames. First, the script copies the webui/ directory verbatim into the project’s build/ directory. Next, the script generates an apigw.js file which contains the API Gateway base URL and the API key to be used by Web UI for invoking the Fetch Frames function deployed in AWS Lambda. This file is created in the Web UI build directory.

You can issue the Web UI build command as follows.

```bash
pynt webui
```

### The `webuiserver` build command

The webuiserver command starts a local, lightweight, Python-based HTTP server on your machine to serve Web UI from the build/web-ui/ directory. Use this command to serve the prototype's Web UI for development and demonstration purposes. You can specify the server’s port as pynt task parameter, between square brackets.

Here’s sample invocation of the command.

```bash
pynt webuiserver # Starts lightweight HTTP Server on port 8080.
```

### The `videocaptureip` and `videocapture` build commands

The videocaptureip command fires up the MJPEG-based video capture client (source code under the client/ directory). This command accepts, as parameters, an MJPEG stream URL and an optional frame capture rate. The capture rate is defined as 1 every X number of frames. Captured frames are packaged, serialized, and sent to the Kinesis Frame Stream. The video capture client for IP cameras uses Open CV 3 to do simple image processing operations on captured frame images – mainly image rotation.

Here’s a sample command invocation.

```bash
pynt videocaptureip["http://192.168.0.2/video",20] # Captures 1 frame every 20.
```

On the other hand, the videocapture command (without the trailing 'ip'), fires up a video capture client that captures frames from a camera attached to the machine on which it runs. If you run this command on your laptop, for instance, the client will attempt to access its built-in video camera. This video capture client relies on Open CV 3 to capture video from physically connected cameras. Captured frames are packaged, serialized, and sent to the Kinesis Frame Stream.

Here’s a sample invocation.

```bash
pynt videocapture[20] # Captures one frame every 20.
```

## Deploy and run the prototype
In this section, we are going use project's build commands to deploy and run the prototype in your AWS account. We’ll use the commands to create the prototype's AWS CloudFormation stack, build and serve the Web UI, and run the Video Cap client.

* Prepare your development environment, and ensure configuration parameters are set as you wish.

* On your machine, in a command line terminal change into the root directory of the project. Activate your virtual Python environment. Then, enter the following commands:

```bash
$ pynt packagelambda #First, package code & configuration files into .zip files

#Command output without errors

$ pynt deploylambda #Second, deploy your lambda code to Amazon S3

#Command output without errors

$ pynt createstack #Now, create the prototype's CloudFormation stack

#Command output without errors

$ pynt webui #Build the Web UI

#Command output without errors
```

* On your machine, in a separate command line terminal:

```bash
$ pynt webuiserver #Start the Web UI server on port 8080 by default
```

* In your browser, access http://localhost:8080 to access the prototype's Web UI. You should see a screen similar to this:

![Empty Web UI](https://moanany-share.s3.amazonaws.com/webui-empty.png?AWSAccessKeyId=AKIAJZICANBOQ5ADZ7YQ&Expires=1530440190&Signature=QtapZYVNvHOPx7aFLxrXCMLUMKc%3D)

* Now turn on your IP camera or launch the app on your smartphone. Ensure that your camera is accepting connections for streaming MJPEG video over HTTP, and identify the local URL for accessing that stream.

* Then, in a terminal window at the root directory of the project, issue this command:

```bash
$ pynt videocaptureip["<your-ip-cam-mjpeg-url>",<capture-rate>]
```
* Or, if you don’t have an IP camera and would like to use a built-in camera:

```bash
$ pynt videocapture[<frame-capture-rate>]
```

* Few seconds after you execute this step, the dashed area in the Web UI will auto-populate with captured frames, side by side with labels recognized in them.

## When you are done
After you are done experimenting with the prototype, perform the following steps to avoid unwanted costs.

* Terminate video capture client(s) (press Ctrl+C in command line terminal where you got it running)
* Close all open Web UI browser windows or tabs.
* Execute the ```pynt deletestack``` command (see docs above)
* After you run ```deletestack```, visit the AWS CloudFormation console to double-check the stack is deleted.
* Ensure that Amazon S3 buckets and objects within them are deleted.

Remember, you can always setup the entire prototype again with a few simple commands.

# License
Licensed under the Amazon Software License.

A copy of the License is located at

[http://aws.amazon.com/asl/](http://aws.amazon.com/asl/)

# The AWS CloudFormation Stack (optional read)

Let’s quickly go through the stack that AWS CloudFormation sets up in your account based on the template. AWS CloudFormation uses as much parallelism as possible while creating resources. As a result, some resources may be created in an order different than what I’m going to describe here.

First, AWS CloudFormation creates the IAM roles necessary to allow AWS services to interact with one another. This includes the following.

* _ImageProcessorLambdaExecutionRole_ – a role to be assumed by the Image Processor lambda function. It allows full access to Amazon DynamoDB, Amazon S3, Amazon SNS, and AWS CloudWatch Logs. The role also allows read-only access to Amazon Kinesis and Amazon Rekognition. For simplicity, only managed AWS role permission policies are used.

* _FrameFetcherLambdaExecutionRole_ – a role to be assumed by the Frame Fetcher lambda function. It allows full access to Amazon S3, Amazon DynamoDB, and AWS CloudWatch Logs. For simplicity, only managed AWS permission policies are used.
In parallel, AWS CloudFormation creates the Amazon S3 bucket to be used to store the captured video frame images. It also creates the Kinesis Frame Stream to receive captured video frame images from the Video Cap client.

Next, the Image Processor lambda function is created in addition to an AWS Lambda Event Source Mapping to allow Amazon Kinesis to trigger Image Processor once new captured video frames are available. 

The Frame Fetcher lambda function is also created. Frame Fetcher is a simple lambda function that responds to a GET request by returning the latest list of frames, in descending order by processing timestamp, up to a configurable number of hours, called the “fetch horizon” (check the framefetcher-params.json file for more run-time configuration parameters). Necessary AWS Lambda Permissions are also created to permit Amazon API Gateway to invoke the Frame Fetcher lambda function.

AWS CloudFormation also creates the DynamoDB table where Enriched Frame metadata is stored by the Image Processor lambda function as described in the architecture overview section of this post. A Global Secondary Index (GSI) is also created; to be used by the Frame Fetcher lambda function in fetching Enriched Frame metadata in descending order by time of capture.

Finally, AWS CloudFormation creates the Amazon API Gateway resources necessary to allow the Web UI to securely invoke the Frame Fetcher lambda function with a GET request to a public API Gateway URL.

The following API Gateway resources are created.

* REST API named “RtRekogRestAPI” by default.

* An API Gateway resource with a path part set to “enrichedframe” by default.

* A GET API Gateway method associated with the “enrichedframe” resource. This method is configured with Lambda proxy integration with the Frame Fetcher lambda function (learn more about AWS API Gateway proxy integration here). The method is also configured such that an API key is required.

* An OPTIONS API Gateway method associated with the “enrichedframe” resource. This method’s purpose is to enable Cross-Origin Resource Sharing (CORS). Enabling CORS allows the Web UI to make Ajax requests to the Frame Fetcher API Gateway URL. Note that the Frame Fetcher lambda function must, itself, also return the Access-Control-Allow-Origin CORS header in its HTTP response.

* A “development” API Gateway deployment to allow the invocation of the prototype's API over the Internet.

* A “development” API Gateway stage for the API deployment along with an API Gateway usage plan named “development-plan” by default.

* An API Gateway API key, name “DevApiKey” by default. The key is associated with the “development” stage and “development-plan” usage plan.

All defaults can be overridden in the cfn-params.json configuration file. That’s it for the prototype's AWS CloudFormation stack! **This stack was designed primarily for development/demo purposes, especially how the Amazon API Gateway resources are set up.**

# FAQ

> **Q: Why is this project titled "amazon-rekognition-video-analyzer" despite the security-focused use case?** 

> **A:** Although this prototype was conceived to address the security monitoring and alerting use case, you can use the prototype's architecture and code as a starting point to address a wide variety of use cases involving low-latency analysis of live video frames with Amazon Rekognition. 
