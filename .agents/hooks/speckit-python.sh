#!/bin/sh
# Points the spec-kit scripts at the project's Python environment, which has PyYAML, for the rest of the session.
# The spec-kit scripts call python3 from the PATH unless these variables name another interpreter.

[ -n "$CLAUDE_ENV_FILE" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Read the environment path the way uv does, because running uv here would create an empty environment when none exists.
venv="${UV_PROJECT_ENVIRONMENT:-.venv}"
case "$venv" in
    /*) ;;
    *) venv="$PWD/$venv" ;;
esac
python="$venv/bin/python"

[ -x "$python" ] || exit 0
"$python" -c 'import yaml' >/dev/null 2>&1 || exit 0

# The file is sourced as shell code, so the path is single-quoted to keep spaces, quotes and $ literal.
quoted="'$(printf '%s' "$python" | sed "s/'/'\\\\''/g")'"
{
    echo "export SPECKIT_PYTHON_EXECUTABLE=$quoted"
    echo "export SPECKIT_PYTHON=$quoted"
} >> "$CLAUDE_ENV_FILE"
