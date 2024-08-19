#!/bin/bash

export INFRAHUB_IMAGE_VER=${REPO_URL##*/}
invoke demo.start
sleep 60
invoke demo.load-infra-schema demo.load-infra-data
invoke demo.stop