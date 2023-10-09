#!/bin/bash

cd /workspace/toto
pyenv install 3.11 --skip-existing
pyenv local 3.11
pip install toml invoke
curl -sSL https://install.python-poetry.org | python3 -
poetry config virtualenvs.create false
poetry install
poetry run invoke demo.build