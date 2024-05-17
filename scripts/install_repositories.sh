#!/bin/sh

# Set janus (test-event-generator) version tag 
export janus_tag=v1.0.0

# clone janus repo
cd /tmp/
if git clone https://github.com/xtuml/janus.git; then
    ERROR=""
else
    ERROR="$(git clone https://github.com/xtuml/janus.git 2>&1 1>/dev/null)"
fi

# check if clone was successful
if [ -z "$ERROR" ]; then
    echo "janus (test-event-generator) cloned successfully"
else
    if [ "$ERROR" == *"fatal: Could not read from remote repository"* ]; then
        echo "janus (test-event-generator) clone failed functionality will not be present in Test Harness."
        exit 0
    else
        >&2 echo "janus (test-event-generator) clone failed with error message:\n$ERROR"
        exit 1
    fi
fi

# fail if errors are encountered
set -e

# navigate to cloned repo and checkout specified version
cd janus
git fetch --all --tags
git checkout tags/$janus_tag -b latest

# install dependencies and the package
pip install -r requirements.txt
pip install .

# clean up
cd ..
rm -f -r janus/