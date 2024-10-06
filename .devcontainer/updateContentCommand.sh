#!/bin/bash

export WEB_CONCURRENCY=2
invoke demo.build demo.start
sleep 120
docker logs infrahub-server-1
invoke demo.load-infra-schema
docker logs infrahub-server-1
sleep 90
docker logs infrahub-server-1
invoke demo.load-infra-data
invoke demo.stop
