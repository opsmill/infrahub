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

# Without an interpreter that has PyYAML, the command runs unchanged and Spec Kit falls back to python3 from the PATH.
if [ -x "$python" ] && "$python" -c 'import yaml' >/dev/null 2>&1; then
    export SPECKIT_PYTHON_EXECUTABLE="$python"
    export SPECKIT_PYTHON="$python"
fi
exec /bin/bash -c "$1"
