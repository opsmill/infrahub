#!/bin/bash

cd /workspace/infrahub

# Dynamic or project-specific setup
poetry install
poetry run invoke demo.build