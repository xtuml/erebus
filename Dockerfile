FROM python:3.11-slim-bullseye


# install pre-requisites and setup folders
RUN apt-get update && yes "yes" | apt-get upgrade && \
    yes "yes" | apt-get install openssh-client && \
    yes "yes" | apt-get install git && \
    mkdir -p -m 0600 /root/.ssh/ && \
    touch /root/.ssh/known_hosts && \
    ssh-keyscan gitlab.com >> /root/.ssh/known_hosts && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts && \
    mkdir /test_harness_app && \
    mkdir /config

RUN --mount=type=ssh pip install git+ssh://git@github.com/SmartDCSITlimited/test-event-generator.git 

WORKDIR /test_harness_app

COPY . /test_harness_app/

RUN --mount=type=ssh chmod +x /test_harness_app/scripts/install_repositories.sh && \
    /test_harness_app/scripts/install_repositories.sh && \
    pip install -r requirements.txt

EXPOSE 8800

ENTRYPOINT [ "python", "-W", "ignore", "-m", "test_harness.run_app", "--harness-config-path", "/config/config.config" ]
