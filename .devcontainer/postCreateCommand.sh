#!/bin/bash

git pull
export INFRAHUB_IMAGE_VER=${REPO_URL##*/}
invoke demo.start