#!/bin/bash

poetry config virtualenvs.create true
poetry config virtualenvs.in-project true
poetry install --no-interaction --no-ansi

export INFRAHUB_IMAGE_VER=${REPO_URL##*/}
invoke demo.start demo.stop
