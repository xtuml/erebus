# Test Harness
Package that runs a test harness for the Munin Protocol Verifier (https://github.com/xtuml/munin/tree/main).

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

***
## Installation and Image Build
***

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
***
It is recommended to deploy the test harness in the same VPC (or private network) as the machine containing the  Protocol Verifier and HTTP Server (see figure below of an example deployment) to avoid exposing the machine to public internet. 

![](./docs/diagrams/deployment/deployment.png)

### <b>HTTP Server</b>
The HTTP server is an intermediary device to allow the test harness to be separated from the PV machine and allows the http requests to upload files and download files (https://gitlab.com/smartdcs1/cdsdt/protocol-verifier-http-server). This can however be replaced by any intermediary as long as the end points server exactly the same purpose.
#### <b>Endpoints</b>
The deployment of the Test Harness must be used in conjuction with an HTTP server that has the following endpoints that provide functionality to upload, download, track and remove files from mounted folders:
* upload
    * `/upload/job-definitions` - End point to upload PV job definitions to <b>Job Definitions</b> folder
    * `/upload/events` - End point to send a file to <b>AER Incoming</b> folder
* download
    * `/download/verifier-log-file-names` - End point to receive the names of the files within <b>Logs Verifier</b> folder that contain the prefix <b>Verifier.log</b>
    * `/download/aer-log-file-names` - End point to receive the names of the files within <b>Logs Reception</b> folder that contain the prefix <b>Reception.log</b> 
    * `/download/verifierlog` - End point to download <b>Verifier.log</b> (or similar name) from the folder <b>Logs Verifier</b>
    * `/download/aerlog` - End point to download <b>Reception.log</b> (or similar name) from the folder <b>Logs Reception</b>
* folder tracking
    * `/ioTracking/aer-incoming` - Endpoint to track the number of files within the <b>AER Incoming</b> folder
    * `/ioTracking/verifier-processed` - Endpoint to track the number of files within the <b>Verifier Processed</b> folder
* folder clean up
    * `/io/cleanup-test` - Endpoint to remove all non hidden files from the folder mounted to the HTTP server
#### <b>Deploy</b>
A pre-built tagged version of the HTTP server compatible with this version of the Test Harness can be found in SmartDCS's GitLab container registry at - `registry.gitlab.com/smartdcs1/cdsdt/protocol-verifier-http-server:0.1.4`.

To deploy the HTTP server the following folders must be mounted (PV folder -> HTTP server):
* `./aeo_svdc_config -> /data/aeo_svdc_config` - AEO SVDC CONFIG Folder mapping
* `./aeo_svdc_config/job_definitions -> /data/aeo_svdc_config/job_definitions` - Job Definitions Folder Mapping
* `./aerconfig -> /data/aerconfig` - AER CONFIG Folder Mapping
* `./aerincoming -> /data/events` - AER Incoming Folder mapping
* `./logs/verifier -> /data/logs/verifier` - Verifier Logs Folder mapping
* `./logs/reception -> /data/logs/reception` - Reception Logs mapping
* `./verifier-processed -> /data/verifier_processed` - Verifier Processed Folder mapping
* `./verifier-incoming -> /data/verifier_incoming` - Verifier Incoming Folder mapping
* `./JobIdStore -> /data/job_id_store` - Job ID Store Folder mapping
* `./InvariantStore -> /data/invariant_store` - Invariant Store Folder mapping

The following Environment Variables must be set:
* `GIN_MODE=release`

The following ports must be forwarded (HTTP -> machine):
* `9000` - `9000`

The following extra arguments to the `docker run` command must be provided:
* `-path=/data`

### <b>Test Harness</b>
#### <b>Pre-requisites</b>
To deploy the test harness one must have at least read access to this repositroy and read access of `registry.gitlab.com/smartdcs1/cdsdt/test-harness` container repository so as to be able to obtain `registry.gitlab.com/smartdcs1/cdsdt/test-harness:MuninP2S1-midstage`.
#### <b>Deployment</b>
The Test Harness can be deployed simply by cloning this repository and navigating to the `deployment` directory from the project root. One can then run the following command:

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
    * `max_files_in_memory` - The number of job files that are allowed to sit in the memory at any one time. Defaults to `10000`
* folder file io tracking
    * `aer_io_url` - The http url of the endpoint that responds with the number of files currently in aer incoming. Defaults to `http://host.docker.internal:9000/ioTracking/aer-incoming`
    * `ver_io_url` - The http url of the endpoint that responds with the number of files currently in verifier processed. Defaults to `http://host.docker.internal:9000/ioTracking/verifier-processed`
    * `io_calc_interval_time` - The interval time between each reading of the folders numbers of files. Defaults to `1`. It is recommended for large workloads (over 100,000) that this value be set to a large value (over 60 seconds or more than the read timeout) to ensure that lots of request that take a long time are not being performed at the same time.   
    * `io_read_timeout` - The read timeout of the requests to track the number of files in the AEReception incoming and Verifier processed folders. Defaults to `300` (seconds). It is recommended for large workloads (over 100,000) files sent that this value be large otherwise requests for io tracking will fail.  
* log reception and finishing time parameters
    * `log_calc_interval_time` - The interval time between requests for the log files. Defaults to `5`
    * `aer_get_file_url` - The url of the endpoint that requests are sent to receive a named log files for AER. Defaults to  `http://host.docker.internal:9000/download/aerlog`
    * `ver_get_file_url` - The url of the endpoint that requests are sent to receive a named log files for the Verifier. Defaults to `http://host.docker.internal:9000/download/verifierlog`
    * `aer_get_file_names_url` - The url of the endpoint that requests are sent to to obtain the names of the AER log files. Defaults to `http://host.docker.internal:9000/download/aer-log-file-names`
    * `ver_get_file_names_url` - The url of the endpoint that requests are sent to to obtain the names of the Verifier log files. Defaults to `http://host.docker.internal:9000/download/verifier-log-file-names`
* Config relating to sending files to the HTTP server
    * `pv_send_url` - The url of the endpoint that requests are sent to to upload events for reception and verification. Defaults to `http://host.docker.internal:9000/upload/events`
    * `pv_send_job_defs_url` - The url of the endpoint that requests are sent to to upload job definitions to. Defaults to `http://host.docker.internal:9000/upload/job-definitions`
* Config that is dependent on the config set on the Protocol Verifier
    * `pv_config_update_time` - The amount of time to wait for the uploaded job definition to be seen by the Protocol Verifier. Defaults to `60` (seconds). This should be greater than the field `SpecUpdateRate` of the PV
    * `pv_finish_interval` - The amount of time thats is required for the Verifier logs to not have updated so that the Test Harness can finish the test. Defaults to `30`. It is recommended that this value be greater than the value of the fields (of the PV config) `MaximumJobTime` and `JobCompletePeriod`
* `pv_clean_folders_url` - The url of the endpoint that requests are sent to that clean the PV folders of all files relating to a test. Defaults to `http://host.docker.internal:9000/io/cleanup-test`
* `pv_clean_folders_read_timeout` - The amount of time to wait for a read timeout when cleaning the Protocol Verifier folders after a test. Defaults to `300` (seconds). It is recommended to set this value reasonably large for tests with a large amount of files.
***
## Usage
***
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
* `max_different_sequences`: `int` `> 0` - Indicates the maximum number of different sequences to use in the tests
* `event_gen_options`: `dict` - Options for event sequence generation using the Test Event Generator. This option contains the following sub-fields: 
    * `solution_limit`: `int` `>= 0` - The max number of solutions to each ILP model in the Test Event Generator. This option can be used to limit how many solutions are found if the possibilities for a job definition are very large.
    * `max_sol_time`: `int` `>= 0` - The maximum time (in seconds) to run an ILP solution in the Test Event Generator. This option should be used to limit the time getting solutions to the ILP models if they are taking too long
    * `invalid`: `True` | `False` : `bool` - Boolean value indicating whether to include invalid sequences or not in the output
    * `invalid_types`: [
    `"StackedSolutions"` | `"MissingEvents"` | `"MissingEdges"` | `"GhostEvents"` | `"SpyEvents"` | `"XORConstraintBreaks"` | `"ANDConstraintBreaks"`
    ] : `list`[`str`] - A list of the invalid solutions to include if `invalid` is set to `True`
* `performance_options`: `dict` - Options for a perfomance test is `type` is set to `"Performance"`. This option contains the folloing sub-fields: 
    * `num_files_per_sec`: `int` `>= 0` - The number of files to send per second to the PV. If used in conjuction with `shard` set to `True` this will send single Events files at the prescribed rate
    * `shard`: `True` | `False` : `bool` - Boolean value indicating whether to shard job sequences into single event files and send them separately
    * `total_jobs`: `int` `>= 0` - The total number of separate jobs to use in the performance test.

#### <b>Example Json test config</b>
```
{
    "type":"Performance",
    "max_different_sequences": 100,
    "event_gen_options": {
        "solution_limit": 100,
        "max_sol_time": 120 
        "invalid": true,
        "invalid_types": [
            "StackedSolutions", "MissingEvents"
        ]
    },
    "performance_options": {
        "num_files_per_sec": 10,
        "total_jobs": 100,
        "shard": false
    }
}
```

#### <b>Exmaple YAML test config</b>
```
type: "Functional"
max_different_sequences: 200
event_gen_options: 
  solution_limit: 100
  max_sol_time: 120
  invalid: False
  invalid_types: [
    "StackedSolutions", "MissingEvents", "MissingEdges",
    "GhostEvents", "SpyEvents", "XORConstraintBreaks",
    "ANDConstraintBreaks"
  ]
performance_options:
  num_files_per_sec: 10
  shard: False
  total_jobs: 100
```

### <b>Flask Service</b>
#### <b>Running the Service</b>
The flask service can be run in two ways:
* Following the instructions in <b>Deployment</b>:<b>Test Harness</b>:<b>Deploy</b> above. The following should then appear in stdout:
    ```
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
    ```
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
A test can be run with the four following stages (`/startTest` endpoint must be run after all the others) once the Flask service is running (two are optional endpoints that may or may not be used):
* Upload of UML files - PUML files that are the graphical representation of a Job Definition must be uploaded before a test can begin. This can be done by sending a POST request with the PUML file/s attached that are needed for the test to the endpoint `/uploadUML`. An example using `curl` is given below:
    
    ```
    curl --location --request POST 'http://127.0.0.1:8800/uploadUML' --form 'file1=@"ANDFork_ANDFork_a.puml"'
    ```
    This should receive a 200 OK response with the following body text `Files uploaded successfully`

* (OPTIONAL) A profile for a performance test can be uploaded as well in the form of a CSV file. The profile provides specific points (given in seconds) in simulation time where the number of test files sent per second is described. The csv must have the following headers in the following order: "Time", "Number". The Test Harness will linearly interpolate between these times to a discretisation of 1 second and will calculate how many test files are sent within that second. The end-point is called `/upload/profile` and is of mime type `multipart/form`. However only one file can be uploaded toherwise the Test Harness will raise an error and not run. An example usage is shown below:
    ```
    curl --location --request POST 'http://127.0.0.1:8800/upload/profile' --form 'file1=@"test_profile.csv"'
    ```

* (OPTIONAL) Test job event files can also be uploaded rather than producing them from the puml file given (note the test files uploaded must correspond to the PUML uploaded otherwise failures of the PV are guarenteed). A test file uploaded must have the following form:
    ```
    {
        "job_file": <list of jsons of PV events>,
        "job_name": <string denoting name of job>,
        "SequenceType": <string denoting the type of sequence for functional tests>,
        "validity": <boolean indicating if the job file is should pass or fail in the PV>
    }
    ```
    An example file is shown below:
    ```
    {
        "job_file": [
            {
                "jobId": "4f57f033-03e9-468c-b3b4-c144af8a3e20",
                "jobName": "test_uml_1",
                "eventType": "A",
                "eventId": "8628fdb6-48e7-4eab-9c9d-95bcbe48b7d0",
                "timestamp": "2023-09-21T14:35:09.728704Z",
                "applicationName": "default_application_name"
            },
            {
                "jobId": "4f57f033-03e9-468c-b3b4-c144af8a3e20",
                "jobName": "test_uml_1",
                "eventType": "B",
                "eventId": "ad46fae5-4970-4e7d-90d2-eb23d83f63ec",
                "timestamp": "2023-09-21T14:35:09.728783Z",
                "applicationName": "default_application_name",
                "previousEventIds": [
                    "8628fdb6-48e7-4eab-9c9d-95bcbe48b7d0"
                ]
            }
        ],
        "job_name": "test_uml_1",
        "sequence_type": "ValidSols",
        "validity": true
    }    
    ```
    The endpoint `/upload/test-files` allows the upload of multiple test files and is of mime type `multipart/form`. An example curl request is shown below:
    ```
    curl --location --request POST 'http://127.0.0.1:8800/upload/test-files' --form 'file1=@"test_uml_1_events.json"'
    ``` 

* Start Tests Once all files required for the test have been uploaded to the harness the test can be started by sending a POST request with the JSON test data attached (must use header `'Content-Type: application/json'`) to the endpoint `/startTest`.

    The JSON can contain (but does not have to) the following fields:
    * `"TestName"`: `str` - A string representing the name of the test. If not provided a random uuid test name will be provided. Once a test is complete a directory will be created with the name given to the test and all report files relating to the test will be found within that directory.
    * `"TestConfig"`: `dict` - A JSON object like that given in <b>Example Json test config</b> above that provides the configuration for the test

    An example of a POST request using curl is provided below:
    ```
    curl -X POST -d '{"TestName": "A_perfomance_test", "TestConfig":{"event_gen_options":{"invalid":false}, "type":"Performance", "performance_options": {"num_files_per_sec":10, "total_jobs":100}}}' -H 'Content-Type: application/json' 'http://127.0.0.1:8800/startTest'
    ```

### <b>CLI Tool</b>
Functionality has been provided to use the Test Harness as a CLI tool.

The test harness CLI can be run from the project root directory using the following command (this will run with default harness config, test config and output report directories):

`python -m test_harness <path to puml job def 1> ... <path to puml job def n>`

As is clear from the above one can use multiple puml files in a test harness run. Currently the following extra arguments are supported:
* `-o` or `--outdir` - Path to the output directory for the test report
* `--harness_config` - Path to a valid harness config file
* `--test_config` - Path to a test config yaml file like the example outlined in <b>Exmaple YAML test config</b>

An example of using the CLI tool with all of the options would be
```
python -m test_harness \
    --outdir <path to report output directory> \
    --harnes_config <path to custom harness config> \ 
    --test_conifg <path to custom test config yaml> \
    <path to puml job def 1> ... <path to puml job def n>`
```

### <b>Test reports</b>
Test reports can be found in a directory named after the `"TestName"` field sent in the POST request to `/startTest` endpoint. These directories are located in the `report_output` directory.
* For a run using the instructions in <b>Deployment</b>:<b>Test Harness</b>:<b>Deploy</b> the report output folder is located at `deployment/report_output` relative to the project root directory
* For a run using the command
    `python -m test_harness.run_app --harness-config-path <path to harness config file>`

    The report output folder is (by default) located at `test_harness/report_output` relative to the porject root directory. One can change this directory by editing the field `report_file_store` in the file `test_harness/config/store_config.config` and changing it to a path of the users choice
* For a run using the CLI tool the report output folder is (by default) located at `test_harness/report_output`. If the `--outdir` option is specified the report files will be saved to the relevant folder.
#### <b>Functional</b>
Within the directory of the specific test a Functional test will produce the following files:
* `Results.xml` - A junit representation of the test results
* `Results.html` - An html representation of the test results
* `Results.csv` - A csv representation of the test results

All of the job files of the test will also be saved within this folder so that if failures have occurred the user is able to pinpoint why the test may have failed.
#### <b>Performance</b>
Within the directory of the specific test a Performance test will produce the following files:
* `Basic_Stats.csv` - This file contains the basic results of the performance test
    * `num_jobs` - The total number of jobs sent 
    * `num_events` - The total number of events sent
    * `average_jobs_per_sec` - Average jobs processed per second
    * `average_events_per_sec` - Averge number of events processed per second
    * `reception_end_time` - The simulation ending time of Reception
    * `verifier_end_time` - The simulation ending time of the Verifier also the end time of the test
* `PV_File_IO.csv` - This file contains the readings of the number of files in AER incoming and Verifier Processed at the given time and the calculated files processed per second
* `PV_File_IO.html` - This provides an interactive plot of the number of files in AER incoming and Verifier Processed at the given time and the calculated files processed per second

