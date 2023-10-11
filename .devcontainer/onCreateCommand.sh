#!/bin/bash

poetry config virtualenvs.create true
poetry install --no-interaction --no-ansi --no-root

invoke demo.build