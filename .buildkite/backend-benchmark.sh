#!/bin/bash

set -e
set -x
trap 'date' DEBUG

pipx install poetry

pyenv install $PYTHON_VERSION
pyenv local $PYTHON_VERSION

poetry install

if ! command -v codspeed-runner &> /dev/null; then
    CODSPEED_RUNNER_VERSION=v2.1.0
    curl -fsSL https://github.com/CodSpeedHQ/runner/releases/download/$CODSPEED_RUNNER_VERSION/codspeed-runner-installer.sh | bash
fi
source "$HOME/.cargo/env"

codspeed-runner --token=$$CODSPEED_TOKEN -- poetry run pytest -v backend/tests/benchmark/ --codspeed
