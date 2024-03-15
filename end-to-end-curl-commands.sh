#!/bin/bash

set -e

# We do a while loop here to keep requesting the uploadUML endpoint until the test harness is up and running
echo "Checking if test harness is up and running by uploading"
while ! curl --location --request POST 'http://127.0.0.1:8800/uploadUML' --form 'file1=@"./tests/test_harness/test_files/test_uml_1.puml"' -s -o /dev/null -w "%{http_code}" | grep -q 200; do
    echo tried to do a curl request to uploadUML endpoint but it failed, trying again in 1 second
    echo printing test harness logs to see what is going on
    docker compose -f ./docker-compose-end-to-end-test.yml logs test-harness | tail 
    sleep 1
done
echo "Uploading test config"
curl -X POST -d '{"TestName": "demo4", "TestConfig":{"event_gen_options":{"invalid":false}, "type":"Performance", "performance_options": {"num_files_per_sec":50, "total_jobs":1500, "shard":true}}}' -H 'Content-Type: application/json' 'http://127.0.0.1:8800/startTest'
echo "Waiting for test to start"
sleep 1