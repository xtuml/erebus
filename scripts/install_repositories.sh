#!/bin/sh

# Fail if any part of this script fails
set -e

# test event generator
cd /tmp/
git clone git@github.com:SmartDCSITlimited/test-event-generator.git
cd test-event-generator
git fetch --all --tags
git checkout tags/MuninP2S1-midstage -b latest
pip install -r requirements.txt
pip install .
cd ..
rm -f -r test-event-generator/