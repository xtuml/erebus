#!/bin/sh

# test event generator
cd /tmp/
if git clone git@github.com:SmartDCSITlimited/test-event-generator.git; then
    ERROR=""
else
    ERROR="$(git clone git@github.com:SmartDCSITlimited/test-event-generator.git 2>&1 1>/dev/null)"
fi
if [ -z "$ERROR" ]; then
    echo "test-event-generator cloned successfully"
else
    if [ "$ERROR" == *"fatal: Could not read from remote repository"* ]; then
        echo "test-event-generator clone failed functionality will not be present in Test Harness.\nIf this is not expected get ssh access to rhe repository:\ngit@github.com:SmartDCSITlimited/test-event-generator.git\n"
        exit 0
    else
        >&2 echo "test-event-generator clone failed with error message:\n$ERROR"
        exit 1
    fi
fi
# fail if anything errors
set -e
cd test-event-generator
git fetch --all --tags
git checkout tags/MuninP2S1-midstage -b latest
pip install -r requirements.txt
pip install .
cd ..
rm -f -r test-event-generator/