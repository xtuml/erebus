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

# plus2json
cd /tmp/
git clone git@github.com:xtuml/plus2json.git
cd plus2json/plus2json
git fetch --all --tags
git checkout tags/MuninP2S1-midstage -b latest
pip install antlr4-tools==0.1
yes "yes" | antlr4 -Dlanguage=Python3 plus2json.g4
cd ..
pip install .
cd ..
rm -f -r plus2json/