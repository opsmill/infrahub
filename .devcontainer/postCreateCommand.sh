#!/bin/bash

git pull
git submodule update
invoke demo.start --wait
