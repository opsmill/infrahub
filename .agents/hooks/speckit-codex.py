#!/usr/bin/env python3
"""Route Codex calls to Spec Kit's bash scripts through the venv wrapper."""

import json
import os
import re
import shlex
import sys
from pathlib import Path


HOOKS_DIR = Path(__file__).resolve().parent
SPECIFY_DIR = HOOKS_DIR.parent.parent / ".specify"
# The rewritten command is approved without asking, so only a command that is one script call qualifies.
SHELL_SYNTAX = re.compile(r"[;&|<>`$(){}\n\\#]")
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")


def is_speckit_script_call(command: str, cwd: str) -> bool:
    if SHELL_SYNTAX.search(command):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    while words and ASSIGNMENT.match(words[0]):
        words.pop(0)
    if words and words[0] in {"bash", "sh"}:
        words.pop(0)
    if not words or not words[0].endswith(".sh"):
        return False
    script = (Path(cwd) / words[0]).resolve()
    return script.is_file() and SPECIFY_DIR in script.parents and "scripts" in script.parts


def main() -> None:
    hook_input = json.load(sys.stdin)
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command")
    if hook_input.get("tool_name") != "Bash" or not isinstance(command, str):
        return
    if not is_speckit_script_call(command, hook_input.get("cwd") or os.getcwd()):
        return

    wrapper = HOOKS_DIR / "speckit-python-run.sh"
    updated_command = f"{shlex.quote(str(wrapper))} {shlex.quote(command)}"
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": {**tool_input, "command": updated_command},
                }
            }
        )
    )


if __name__ == "__main__":
    main()
