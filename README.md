# Test Harness
Package that runs a test harness for the Munin Protocol Verifier (https://github.com/xtuml/munin/tree/main).

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

***
## Installation and Image Build
***

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
    * `io_calc_interval_time` - The interval time between each reading of the folders numbers of files. Defaults to `1`
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
[non-default]
***
## Usage
***

***
## License
***
For open source projects, say how it is licensed.

