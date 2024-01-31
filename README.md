# Test Harness
Package that runs a test harness for arbitrary system functional and performance testing. Provides base functionality to set up tests and send test files.

## Installation and Image Build

### Quickstart
On MacOS, you can run the test harness with:
```sh
ssh-add --apple-use-keychain ~/.ssh/id_rsa # Add your private key used for SSH to apple keychain
docker compose up --build
```
NOTE: If the above doesn't work, check that you can access gitlab via git without user interaction (e.g. if you've added your SSH key to the apple keychain).

### <b>Pre-requisites</b>
To install and build this project one must have the following pre-requisites:
* python 3.11 (https://docs.python.org/3/whatsnew/3.11.html) and pip (or other python package manager) be installed on the machine that will be hosting the Test Harness (installation only)
* SSH access to the following git repositories:
    * https://gitlab.com/smartdcs1/cdsdt/test-event-generator
    * https://github.com/xtuml/plus2json 
* Docker installed on the machine (build only)


### <b>Installation</b>
The project can be installed on the machine by choosing the project root directory as the working directory and running the following sequence of commands (it is recommended that a python virtual environment is set up so as not to pollute the main install):

* `./scripts/install_repositories.sh`
* `python3.11 -m pip install -r requirements.txt`

### <b>Build Image</b>
To build the docker image you must first be located in the project root directory and then run the following command (this assumes your ssh keys are in the default location on your machine):

`docker build -t <name(:optional tag)> --ssh default .`

***
## Deployment
It is recommended to deploy the test harness in the same VPC (or private network) as the machine containing the system to be tested to avoid exposure to the public internet. 

![](./docs/diagrams/deployment/deployment.png)

### <b>Test Harness</b>
#### <b>Deployment</b>
The Test Harness can be deployed simply by cloning this repository and navigating to the `deployment` directory from the project root. The build instructions can then be followed (tagging the test harness image as `test-harness:latest`). One can then run the following command (the stock dock):

`docker compose up`

To stop the Test Harness container one can either use `Ctrl+C` or if the process is in the background (making sure you are in the `deployment` directory)

`docker compose stop`.

To destroy the containers run (in `deployment` directory)

`docker compose down`
#### <b>Configuration</b>
Default configuration for running the Test Harness can be found in the file `test_harness/config/default_config.config` (relative to the project root directory). This file contains default values for parameters that control the Test Harness. When deploying a bespoke Test Harness config the file must be placed in `deployment/config` and must have the name `config.config`.

To change default values of these files a parameter can be copied under the `[non-default]` heading in the file and set to a different value. Descriptions for parameters follows:
* General config
    * `requests_max_retries` - The number of times a synchronous request will retry to get the correct response before providing the wrong response. Defaults to `5`
    * `requests_timeout` - The timeout in seconds of a sychronous request. Defaults to `10`
* log reception and finishing time parameters
    * `log_calc_interval_time` (deprecated and can be set in test config under `test_finish` under subfield `metrics_get_interval` in the test config) - The interval time between requests for the log files. Defaults to `5`
* Config relating to metrics collections
    * Kafka metrics collection config
        * `metrics_from_kafka` - Boolean indicating whether to collect metrics from a kafka topic. Defaults to `False``
        * `kafka_metrics_host` - The kafka host to collect the metrics from. Defaults to `host.docker.internal:9092`
        * `kafka_metrics_topic` - The topic to colect the metrics from. Defaults to `default.BenchmarkingProbe_service0`
        * `kafka_metrics_collection_interval` - An integer indicating the interval, in seconds, in which to collect metrics. Defaults to 1.
* Config relating to sending files
    * `message_bus_protocol` - The protocol to use for sending data to the application being tested. Currently supports the following two values (this will default to HTTP if any inccorect config is given):
        * HTTP - use the HTTP protocol to send data
        * KAFKA - use kafka to send data
        * KAFKA3 - use the kafka3 module for sending data (can be more performant)
    * Config relating to sending files to Kafka (if `message_bus_protocol` is set to "KAFKA" | "KAFKA3")
        * `kafka_message_bus_host` - The kafka host to send message to. Defaults to  `host.docker.internal:9092`
        * `kafka_message_bus_topic` The kafka topic to send messages to. Defaults to  `default.AEReception_service0`
    * Config relating to sending files to the HTTP server (if `message_bus_protocol` is set to "HTTP") TODO: Change this to reflect an arbitrary test
        * `pv_send_url` - The url of the endpoint that requests are sent to to upload events for reception and verification. Defaults to `http://host.docker.internal:9000/upload/events`
***
## Usage
Currently there are two main ways to use the Test Harness:
* Flask Service - A flask service that serves http requests to run the test harness
* Command Line Interface (CLI) Tool

The basic usage of each of these methods is outlines below along with an overview of the test configuration that can be used.
### <b>Test Configuration</b>
Test configuration can be provided to the test harness in the form of:
* Json when starting the test using the Flask Service
* A yaml file when using the CLI Tool

The fields within the json and yaml file are as follows:

* `type`: `"Functional"` | `"Perfomance"` : `str` - Indicates if the test is to be
    * `"Functional"` - A test of the functionality of the PV
    * `"Perfomance"` - A test of the performance of the PV 
* `performance_options`: `dict` - Options for a perfomance test is `type` is set to `"Performance"`. This option contains the folloing sub-fields: 
    * `num_files_per_sec`: `int` `>= 0` - A uniform rate of the number of test events to produce per second for sending to the system when no profile has been uploaded. 
* `num_workers`: `int` - The number of worker processes to use for sending files. If this is equal to an integer of `0` or anything less the program will run in serial. If not equal to an integer the program will fail. Defaults to `0` and runs in serial.
* `aggregate_during`: `bool` - Boolean indicating whether to aggregate metrics during a test (`True`) or not (`False`). There is a small performance penalty for aggregating metrics during a test as the aggregations are computed on the fly. If `low_memory` option is set to `True` the input value from the user is ignored and metrics are aggregated during the test.  Defaults to `False` otherwise.
* `sample_rate`: `int` - Integer indicating the approximate number of "events" to sample per second (calculates a probability of `min(1, sample_rate/actual_rate)`) when saving results as the test proceeds for calculating metrics after the test is complete. If set to `0` or lower no sampling is performed. Defaults to `0`
* `low_memory`: `bool` - Boolean indicating whether to save results to memory/disk (`False`) or not (`True`) as the test proceeds. If set to `True` any metrics (calculated over time) that rely on knowing information when each "event" is sent and when it is received or processed by the system (this could be an unbounded amount of time before all quantities are available) cannot be calculated e.g. response times, queue times etc. If set to `True`, `aagregate_during` value is ignored and metrics are aggregated during the test. Defaults to `False`
* `test_finish`: `dict` - Options stopping a test. This option contains the following sub-fields: ,
   * `metric_get_interval`: `int` => 0, defaults to 5 - The interval with which to grab metrics that determine the end of a test
   * `finish_interval`: `int` => 0, defaults to 30 - The interval with which to calculate the end of a test if there has been no change in the grabbed metrics within that time. Should some integer multiple of `metric_get_interval`
   * `timeout`: `int` => 0, defaults to 120 - Time to wait before ending the test after all test data has been sent.

#### <b>Example Json test config</b>
```json
{
    "type":"Performance",
    "performance_options": {
        "num_files_per_sec": 10,
    },
    "num_workers": 0,
    "aggregate_during": false,
    "sample_rate": 0,
    "low_memory": false
}
```

#### <b>Exmaple YAML test config</b>
```yaml
type: "Functional"
performance_options:
  num_files_per_sec: 10
num_workers: 0
aggregate_during: False
sample_rate: 0
low_memory: False
```

### <b>Flask Service</b>
#### <b>Running the Service</b>
The flask service can be run in two ways:
* Following the instructions in <b>Deployment</b>:<b>Test Harness</b>:<b>Deploy</b> above. The following should then appear in stdout:
    ```sh
    [+] Building 0.0s (0/0)                                                             
    [+] Running 2/2
     ✔ Network test-harness_default           Cr...                                0.1s 
     ✔ Container test-harness-test-harness-1  Created                              0.0s 
    Attaching to test-harness-test-harness-1
    test-harness-test-harness-1  | INFO:root:Test Harness Listener started
    test-harness-test-harness-1  |  * Serving Flask app 'test_harness'
    test-harness-test-harness-1  |  * Debug mode: off
    test-harness-test-harness-1  | INFO:werkzeug:WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
    test-harness-test-harness-1  |  * Running on all addresses (0.0.0.0)
    test-harness-test-harness-1  |  * Running on http://127.0.0.1:8800
    test-harness-test-harness-1  |  * Running on http://172.24.0.2:8800
    test-harness-test-harness-1  | INFO:werkzeug:Press CTRL+C to quit
    ```

* Following the instructions in <b>Installation and Image Build</b>:<b>Installation</b> and then running the following command from the project root (with a custom harness config file)

    `python -m test_harness.run_app --harness-config-path <path to harness config file>`

    Once one of this has been followed the following should appear in stdout of the terminal:
    ```sh
    INFO:root:Test Harness Listener started
     * Serving Flask app 'test_harness'
     * Debug mode: off
    INFO:werkzeug:WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
     * Running on all addresses (0.0.0.0)
     * Running on http://127.0.0.1:8800
     * Running on http://172.17.0.3:8800
    INFO:werkzeug:Press CTRL+C to quit
    ```
#### <b>Running a Test</b>
An arbitrary test can be run with the any of the three following stages before running the `/startTest` endpoint,  once the Flask service is running:
* (OPTIONAL) A profile for a performance test can be uploaded as well in the form of a CSV file. The profile provides specific points (given in seconds) in simulation time where the number of test files sent per second is described. The csv must have the following headers in the following order: "Time", "Number". The Test Harness will linearly interpolate between these times to a discretisation of 1 second and will calculate how many test files are sent within that second (more info can be found in `docs/TestProfiles.md`). The end-point is called `/upload/profile` and is of mime type `multipart/form`. However only one file can be uploaded toherwise the Test Harness will raise an error and not run. An example usage is shown below:
    ```sh
    curl --location --request POST 'http://127.0.0.1:8800/upload/profile' --form 'file1=@"test_profile.csv"'
    ```

* (OPTIONAL) Test job files can be uploaded that suit the specific system being tested The endpoint `/upload/test-files` allows the upload of multiple test files and is of mime type `multipart/form`. An example curl request is shown below:
    ```sh
    curl --location --request POST 'http://127.0.0.1:8800/upload/test-files' --form 'file1=@"test_file"'
    ``` 

* (RECOMMENDED) (OPTIONAL) This is the recommed way of gettingTest Case zip files may be uploaded to the Test Harness. These can include all the test data required to run the specific test. The zip file structure can vary based on the specific system tested but the basic implementation of the zip file would have the following structure unzipped
    ```sh
    TCASE
    ├── profile_store (optional)
    │   └── test_profile.csv (optional)
    ├── test_config.yaml (optional)
    └── test_file_store (optional)
        ├── test_data_1 (optional)
        └── test_data_2 (optional)
    ```
    Note that all folders and files are optional in general within the zip file (this may not be the case for specific systems for example the `test_file_store` may need to be populated with template test data if the test for the specific system in question does not have a generator of test data). The folder can include:
    * `profile_store` - (OPTIONAL) This can be populated with a single profile for the test case detailing the time dependent rate at which single instances of test data will be sent.
    * `test_file_store` - (OPTIONAL) This can be populted with arbitary template (or otherwise) test data that will be used in the test
    * `test_config.yaml` - (OPTIONAL) This yaml file includes the test config used for the particular test case. If not present the test config in the JSON body of the `startTest` endpoint will be used (along with any defaults not set in the input config)
    
    The endpoint `/upload/named-zip-files` allows the upload of multiple test case zip file and is of mime type `multipart/form`. The file object name of the zip file in the form will be used to create the `TestName` (this is the name that needs to be input in the JSON body under the `TestName` field used with the `startTest` endpoint to run the test case) and will create a folder in the `report_output` folder under which all test data will be saved (WARNING: if the test name already exists this will overwrite all previous data within the output folder) An example curl request to upload a single test case zip file is shown below:
    ```sh
    curl --location --request POST 'http://127.0.0.1:8800/upload/named-zip-files' --form '<TestName here>=@"<Test zip file path>"'
    ``` 
* Start Tests Once all files required for the test have been uploaded to the harness the test can be started by sending a POST request with the JSON test data attached (must use header `'Content-Type: application/json'`) to the endpoint `/startTest`.

    The JSON can contain (but does not have to) the following fields:
    * `"TestName"`: `str` - A string representing the name of the test. If not provided a random uuid test name will be provided. Once a test is complete a directory will be created with the name given to the test and all report files relating to the test will be found within that directory. If a user would like to run a test case that has been uploaded using the `/upload/named-zip-files` endpoint then this field should refer to the file object name part of the form in that previous request.
    * `"TestConfig"`: `dict` - A JSON object like that given in <b>Example Json test config</b> above that provides the configuration for the test

    An example of a POST request using curl is provided below:
    ```sh
    curl -X POST -d '{"TestName": "A_perfomance_test", "TestConfig":{"type":"Performance", "performance_options": {"num_files_per_sec":10}}}' -H 'Content-Type: application/json' 'http://127.0.0.1:8800/startTest'
    ```
#### <b>Stopping a Test</b>
To stop a test gracefully once it is running one must send a POST request with a JSON body (must use header `'Content-Type: application/json'`) to the endpoint `/stopTest`. Currently the JSON accepted is empty. If succesful the response will be a `200 OK` and `400` if not. An example request is provided below:
```sh
curl -X POST -d '{}' -H 'Content-Type: application/json' 'http://127.0.0.1:8800/stopTest'
```
#### <b>Retrieving Output Data</b>
To retrieve output data from a finished test a POST request can be sent to the endpoint `/getTestOutputFolder` with a JSON body (must use header 'Content-Type: application/json'). The JSON body should specify the `TestName` given in the `/startTest` endpoint requets used to start the test. The JSON body should have the following form
```json
{
    "TestName": <name of test as string>
}
```
A correctly formed request will receive a response of a zip file (mime type `application/zip`) containing all the test output data within the folder at that time.
```sh
curl -X POST -d '{"TestName": "test_1"}' -H 'Content-Type: application/json' 'http://127.0.0.1:8800/getTestOutputFolder'
```
An example curl request to this endpoint is as follows 
### <b>CLI Tool</b>
**WARNING this functionality is currently not working and will be updated **

Functionality has been provided to use the Test Harness as a CLI tool.

The test harness CLI can be run from the project root directory using the following command (this will run with default harness config, test config and output report directories):

`python -m test_harness`

Currently the following extra arguments are supported:
* `-o` or `--outdir` - Path to the output directory for the test report
* `--harness_config` - Path to a valid harness config file
* `--test_config` - Path to a test config yaml file like the example outlined in <b>Exmaple YAML test config</b>

An example of using the CLI tool with all of the options would be
```sh
python -m test_harness \
    --outdir <path to report output directory> \
    --harnes_config <path to custom harness config> \ 
    --test_conifg <path to custom test config yaml>
```

### <b>Test reports</b>
Test reports can be found in a directory named after the `"TestName"` field sent in the POST request to `/startTest` endpoint. These directories are located in the `report_output` directory.
* For a run using the instructions in <b>Deployment</b>:<b>Test Harness</b>:<b>Deploy</b> the report output folder is located at `deployment/report_output` relative to the project root directory
* For a run using the command
    `python -m test_harness.run_app --harness-config-path <path to harness config file>`

    The report output folder is (by default) located at `test_harness/report_output` relative to the project root directory. One can change this directory by editing the field `report_file_store` in the file `test_harness/config/store_config.config` and changing it to a path of the users choice
* For a run using the CLI tool the report output folder is (by default) located at `test_harness/report_output`. If the `--outdir` option is specified the report files will be saved to the relevant folder.
#### <b>Functional</b>
Arbitrary functional results
#### <b>Performance</b>
Arbitrary performance results

## Current Testable Systems
### Protocol Verifier
The Protocol Verifier (https://github.com/xtuml/munin) is a system that is supported to be tested byt the Tests Harness. Documentation specifically related to deployment and usage can be found in `docs/protocol_verifier/README.md`
