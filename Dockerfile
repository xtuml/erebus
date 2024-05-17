FROM python:3.11-slim-bullseye


# install pre-requisites and setup folders
RUN apt-get update && yes "yes" | apt-get upgrade && \
    yes "yes" | apt-get install git && \
    mkdir /test_harness_app && \
    mkdir /config

# Install python package test-event-generator from open source repo
RUN pip install git+https://github.com/xtuml/janus.git 

WORKDIR /test_harness_app

COPY . /test_harness_app/

RUN chmod +x /test_harness_app/scripts/install_repositories.sh && \
    /test_harness_app/scripts/install_repositories.sh && \
    pip install -r requirements.txt

EXPOSE 8800

ENTRYPOINT [ "python", "-W", "ignore", "-m", "test_harness.run_app", "--harness-config-path", "/config/config.config" ]
