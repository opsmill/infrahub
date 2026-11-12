#!/bin/sh
# Codex PreToolUse hook entry point. See ../python/route_codex.py.
exec python3 "$(dirname -- "$0")/../python/route_codex.py"
