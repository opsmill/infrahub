#!/bin/bash

git pull
git submodule update
poetry run invoke demo.start --wait
