#!/bin/bash
set -e

export logs_path=.

echo "Removing the application..."
[[ ! $(echo $PV_COMPOSE_FILE) ]] && PV_COMPOSE_FILE="docker-compose-1AER_1AEO.yml"
docker compose -f ${PV_COMPOSE_FILE} down

echo "Done."

echo "Cleaning work directories"
rm -rf ${logs_path}/logs/reception ${logs_path}/logs/verifier InvariantStore JobIdStore config/job_definitions/*
echo "Done"

echo "Pruning system"
docker system prune --force
[[ $(sudo docker volume ls | grep -v "munin_ConanCache" |  awk 'NR>1 {print $2}') ]] && docker volume rm $(sudo docker volume ls | grep -v "munin_ConanCache" |  awk 'NR>1 {print $2}')
echo "Done"
