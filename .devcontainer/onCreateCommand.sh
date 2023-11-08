#!/bin/bash

poetry config virtualenvs.create true
poetry install --no-interaction --no-ansi

invoke demo.build