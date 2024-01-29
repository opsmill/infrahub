#!/bin/bash

set -e
set -x
trap 'date' DEBUG

pip install ruff==0.1.8
ruff check --diff .
ruff format --check --diff .
