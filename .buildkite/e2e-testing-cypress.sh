#!/bin/bash

set -e
set -x
trap 'date' DEBUG

(cd frontend && npm install)

pip install toml invoke

export INFRAHUB_BUILD_NAME="infrahub-$(hostname)"
export INFRAHUB_SERVER_PORT=$(shuf -n 1 -i 10000-60000)

invoke demo.build
invoke demo.pull
invoke demo.destroy
invoke demo.start
invoke demo.load-infra-schema

invoke demo.status
invoke demo.load-infra-data

export INFRAHUB_ADDRESS="http://localhost:${INFRAHUB_SERVER_PORT}"

invoke demo.infra-git-import demo.infra-git-create

(cd frontend && npm run cypress:run:e2e)

docker ps -a
docker logs "${INFRAHUB_BUILD_NAME}-infrahub-server-1"
docker logs "${INFRAHUB_BUILD_NAME}-infrahub-git-1"
docker logs "${INFRAHUB_BUILD_NAME}-infrahub-git-2"
docker logs "${INFRAHUB_BUILD_NAME}-database-1"

invoke demo.status
