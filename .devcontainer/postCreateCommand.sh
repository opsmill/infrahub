#!/bin/bash

git pull
git submodule update
uv run invoke demo.start --wait
