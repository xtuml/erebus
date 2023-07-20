#!/bin/sh
cd /tmp/
git clone git@gitlab.com:smartdcs1/cdsdt/test-event-generator.git
cd test-event-generator
git checkout CDSDT-41-test-event-generator
pip install -r requirements.txt
pip install .
cd ..
rm -f -r test-event-generator/