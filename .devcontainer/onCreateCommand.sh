#!/bin/bash

cat /proc/cpuinfo /proc/meminfo

poetry config virtualenvs.create true
poetry config virtualenvs.in-project true
poetry install --no-interaction --no-ansi

git submodule update --init

invoke demo.build
