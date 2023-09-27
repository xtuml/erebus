#!/bin/sh

# test event generator
cd /tmp/
git clone git@gitlab.com:smartdcs1/cdsdt/test-event-generator.git
cd test-event-generator
git fetch --all --tags
git checkout tags/MuninP2S1-midstage -b latest
pip install -r requirements.txt
pip install .
cd ..
rm -f -r test-event-generator/