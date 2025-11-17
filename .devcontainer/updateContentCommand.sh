#!/bin/bash

export WEB_CONCURRENCY=2
uv run invoke demo.start
sleep 120
docker logs infrahub-server-1
uv run invoke demo.load-infra-schema
docker logs infrahub-server-1
sleep 90
docker logs infrahub-server-1
uv run invoke demo.load-infra-data
uv run invoke demo.stop
