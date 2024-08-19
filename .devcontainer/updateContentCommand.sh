#!/bin/bash

invoke demo.build demo.start
sleep 60
docker logs infrahub-infrahub-server-1
invoke demo.load-infra-schema
sleep 60
invoke demo.load-infra-data
invoke demo.stop