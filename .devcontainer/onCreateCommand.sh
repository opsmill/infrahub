#!/bin/bash

cat /proc/cpuinfo /proc/meminfo

git submodule update --init

uv sync --all-groups

uv run invoke demo.pull
