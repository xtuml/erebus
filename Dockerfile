FROM python:3.11-slim-bullseye


# install pre-requisites and setup folders
RUN apt-get update && yes "yes" | apt-get upgrade && \
    yes "yes" | apt-get install git && \
    mkdir /test_harness_app && \
    mkdir /config

# Install python package test-event-generator from open source repo
RUN pip install git+https://github.com/xtuml/janus.git 

WORKDIR /test_harness_app

# Caches packages installed by pip
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . /test_harness_app/

RUN chmod +x /test_harness_app/scripts/install_repositories.sh && \
    /test_harness_app/scripts/install_repositories.sh

EXPOSE 8800

ENTRYPOINT [ "python", "-W", "ignore", "-m", "test_harness.run_app", "--harness-config-path", "/config/config.config" ]
