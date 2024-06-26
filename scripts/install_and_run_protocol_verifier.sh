#!/bin/bash

# This script automates the process of pulling the latest tagged version of the protocol verifier,
# updating necessary files, and running the protocol verifier using Docker Compose. It ensures
# that the setup is configured correctly to pass functional and performance tests.

# If using the test harness and protocol verifier on an external server, to access the Swagger UI
# you must port forward when gaining ssh access
# ssh -L 8800:localhost:8800 <user_name>@<host_ip_address>

# NOTE: This script should be run within the root directory of erebus
# ./scripts/install_and_run_protocol_verifier.sh

# Get user input for IP address of where protocol verifier is being hosted 
echo "Please enter the IP address of the host network:"
read host_network

# Change working directory to root and pull munin repo
git clone https://github.com/xtuml/munin.git
cd munin

# returns latest tag sorted by date in the form refs/tags/<tag_name>
latest_pv_tag_ref=$(git for-each-ref --sort=creatordate --format '%(refname)' refs/tags | tail -1)

# format latest tag to just <tag_name>
latest_pv_tag=${latest_pv_tag_ref:10}

echo "Checking out latest tag: $latest_pv_tag"
git checkout tags/$latest_pv_tag

# Copy specific files over to munin repo to get tests to pass
echo "Copying over required property files to munin"
cd ..
cp ./end_to_end_test_files/log-pv-files.properties ./munin/deploy/config/log-pv-files.properties
cp ./end_to_end_test_files/log-pv-kafka.properties ./munin/deploy/config/log-pv-kafka.properties

echo "Replacing docker compose file within munin /deploy"
cp ./end_to_end_test_files/docker-compose.prod.yml ./munin/deploy/docker-compose.yml

mkdir -p ./config

echo "Copying config file"
cp ./test_harness/config/default_config.config ./config/config.config

# Update config file with host network IP address
sed -i "s/host.docker.internal/$host_network/g" ./config/config.config

# Update IP address for KAFKA_ADVERTISED_LISTENERS within copied docker-compose
sed -i "s/172.17.0.1/$host_network/g" ./munin/deploy/docker-compose.yml

echo "Starting up the protocol verifier"
sudo docker compose -f ./munin/deploy/docker-compose.yml up -d

echo "Starting up the test harness"
sudo docker compose -f ./docker-compose.yml up -d