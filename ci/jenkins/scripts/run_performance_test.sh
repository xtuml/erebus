#!/bin/bash
set -e

export logs_path=.

echo "Cleaning previous work directories"
rm -rf ${logs_path}/logs/reception ${logs_path}/logs/verifier InvariantStore JobIdStore config/job_definitions/*
echo "Done"

echo "Making new work directories"
mkdir -p ${logs_path}/logs/reception ${logs_path}/logs/verifier InvariantStore JobIdStore
echo "Done"

echo "Launching the application..."
export CONFIG_FILE=benchmarking-config.json
docker compose -f ${PV_COMPOSE_FILE} up -d --wait &>/dev/null
echo "Done."
