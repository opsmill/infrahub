#!/bin/bash

set -e
set -x
trap 'date' DEBUG

(cd frontend && npm install)

pip install toml invoke

export INFRAHUB_BUILD_NAME="infrahub-$(hostname)"
export INFRAHUB_SERVER_PORT=$(shuf -n 1 -i 10000-60000) # TODO: use a more deterministic method

invoke demo.build
invoke demo.pull
invoke demo.destroy
invoke demo.start
invoke demo.load-infra-schema

invoke demo.status
invoke demo.load-infra-data

export INFRAHUB_ADDRESS="http://localhost:${INFRAHUB_SERVER_PORT}"

invoke demo.infra-git-import demo.infra-git-create

if [ "$E2E_TEST_FRAMEWORK" = "playwright" ]; then
    (cd frontend && npx playwright install chromium && npm run ci:test:e2e)
else
    export CYPRESS_BASE_URL=$INFRAHUB_ADDRESS
    (cd frontend && npm run cypress:run:e2e)
fi

docker ps -a
docker logs "${INFRAHUB_BUILD_NAME}-infrahub-server-1"
docker logs "${INFRAHUB_BUILD_NAME}-infrahub-git-1"
docker logs "${INFRAHUB_BUILD_NAME}-infrahub-git-2"
docker logs "${INFRAHUB_BUILD_NAME}-database-1"

invoke demo.status
