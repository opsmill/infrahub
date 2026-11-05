#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: speckit-python-run.sh <shell command>" >&2
    exit 2
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
python=${SPECKIT_PYTHON_EXECUTABLE:-${SPECKIT_PYTHON:-}}

if [ -z "$python" ]; then
    venv=${UV_PROJECT_ENVIRONMENT:-.venv}
    case "$venv" in
        /*) ;;
        *) venv="$repo_root/$venv" ;;
    esac
    python="$venv/bin/python"
elif [ "${python#/}" = "$python" ]; then
    python="$repo_root/$python"
fi

if [ ! -x "$python" ]; then
    echo "Spec Kit needs a project Python interpreter, but '$python' is not executable." >&2
    exit 1
fi

if ! "$python" -c 'import yaml' >/dev/null 2>&1; then
    echo "Spec Kit needs PyYAML. Install project dependencies or set SPECKIT_PYTHON_EXECUTABLE to an interpreter that can import yaml." >&2
    exit 1
fi

export SPECKIT_PYTHON_EXECUTABLE="$python"
export SPECKIT_PYTHON="$python"
exec /bin/bash -c "$1"
