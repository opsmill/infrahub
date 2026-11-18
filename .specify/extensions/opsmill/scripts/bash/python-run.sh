#!/bin/sh
# Runs one shell command with the Spec Kit scripts pointed at the project's Python environment.
# The Codex hook (route-codex.sh) wraps the Spec Kit scripts that need PyYAML in this script.
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: python-run.sh <shell command>" >&2
    exit 2
fi

# This script is installed at .specify/extensions/opsmill/scripts/bash/.
repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../../../../.." && pwd)
venv=${UV_PROJECT_ENVIRONMENT:-.venv}
case "$venv" in
    /*) ;;
    *) venv="$repo_root/$venv" ;;
esac
# A linked worktree might have no environment of its own, so the main checkout's is tried last.
main_venv=
common=$(git -C "$repo_root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || common=
case "$common" in
    */.git) main_venv="${common%/.git}/${UV_PROJECT_ENVIRONMENT:-.venv}" ;;
esac

# Without an interpreter that has PyYAML, the command runs unchanged and Spec Kit falls back to python3 from the PATH.
for python in "${SPECKIT_PYTHON_EXECUTABLE:-}" "${SPECKIT_PYTHON:-}" "$venv/bin/python" "${main_venv:+$main_venv/bin/python}"; do
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
