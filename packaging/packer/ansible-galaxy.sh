#!/bin/sh

cd ansible

if ! poetry run ansible-galaxy --version >/dev/null; then
    poetry install --no-root
fi

poetry run ansible-galaxy "$@"
