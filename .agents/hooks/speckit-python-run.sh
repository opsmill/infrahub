#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: speckit-python-run.sh <shell command>" >&2
    exit 2
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
venv=${UV_PROJECT_ENVIRONMENT:-.venv}
case "$venv" in
    /*) ;;
    *) venv="$repo_root/$venv" ;;
esac

# Without an interpreter that has PyYAML, the command runs unchanged and Spec Kit falls back to python3 from the PATH.
for python in "${SPECKIT_PYTHON_EXECUTABLE:-}" "${SPECKIT_PYTHON:-}" "$venv/bin/python"; do
    case "$python" in
        "") continue ;;
        */*) ;;
        *) python=$(command -v "$python") || continue ;;
    esac
    # The command can change directory, so a relative path is made absolute.
    case "$python" in
        /*) ;;
        *) python="$PWD/$python" ;;
    esac
    if "$python" -c 'import yaml' >/dev/null 2>&1; then
        export SPECKIT_PYTHON_EXECUTABLE="$python"
        export SPECKIT_PYTHON="$python"
        break
    fi
done
exec sh -c "$1"
