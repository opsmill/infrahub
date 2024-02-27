#!/bin/sh

cd ansible

if ! poetry run ansible-playbook --version >/dev/null; then
    poetry install --no-root
fi

poetry run ansible-playbook "$@"
