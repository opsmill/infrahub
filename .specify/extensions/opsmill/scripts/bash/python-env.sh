#!/bin/sh
# Claude Code session start: points the Spec Kit scripts at the project's Python environment for the
# rest of the session, when that environment can import PyYAML. Does nothing otherwise.
# The Spec Kit scripts call python3 from the PATH unless these variables name another interpreter.

[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Read the environment path the way uv does, because running uv here would create an empty
# environment when none exists.
venv="${UV_PROJECT_ENVIRONMENT:-.venv}"
case "$venv" in
    /*) ;;
    *) venv="$PWD/$venv" ;;
esac
python="$venv/bin/python"

# A linked worktree might have no environment of its own, so the main checkout's is used instead.
# The Spec Kit scripts only need PyYAML from it.
if ! "$python" -c 'import yaml' >/dev/null 2>&1; then
    common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
    case "$common" in
        */.git) python="${common%/.git}/${UV_PROJECT_ENVIRONMENT:-.venv}/bin/python" ;;
        *) exit 0 ;;
    esac
    "$python" -c 'import yaml' >/dev/null 2>&1 || exit 0
fi

# The file is sourced as shell code, so the path is single-quoted to keep spaces, quotes and $ literal.
quoted="'$(printf '%s' "$python" | sed "s/'/'\\\\''/g")'"
{
    echo "export SPECKIT_PYTHON_EXECUTABLE=$quoted"
    echo "export SPECKIT_PYTHON=$quoted"
} >> "$CLAUDE_ENV_FILE"
