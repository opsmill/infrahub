#!/bin/bash

export WEB_CONCURRENCY=2
poetry run invoke demo.start
sleep 120
docker logs infrahub-server-1
poetry run invoke demo.load-infra-schema
docker logs infrahub-server-1
sleep 90
docker logs infrahub-server-1
poetry run invoke demo.load-infra-data
poetry run invoke demo.stop
