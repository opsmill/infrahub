#!/usr/bin/env python3
"""Route Codex calls to Spec Kit's bash scripts through the venv wrapper."""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


HOOKS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOKS_DIR.parent.parent
# The rewritten command is approved without asking, so only one exact form is accepted, with nothing that bash could read differently.
SCRIPT_CALL = re.compile(
    r"[ \t]*(?:(?:ba)?sh[ \t]+)?"
    r"(?P<quote>['\"]?)(?:(?P<root>/[^'\"$`\\\x00-\x1f\x7f]+)/)?"
    r"(?P<script>\.specify/(?:extensions/[a-z0-9-]+/)?scripts/bash/[a-z0-9-]+\.sh)(?P=quote)"
    r"(?:[ \t]+[A-Za-z0-9_./:=@+,-]+)*[ \t]*"
)
# Inside quotes, a checkout path may hold spaces and other characters that bash reads literally there.
UNQUOTED_ROOT = re.compile(r"/[A-Za-z0-9_./-]+")


def is_speckit_script_call(command: str, cwd: str) -> bool:
    match = SCRIPT_CALL.fullmatch(command)
    if match is None:
        return False
    if match.group("root") and not match.group("quote") and not UNQUOTED_ROOT.fullmatch(match.group("root")):
        return False
    root = match.group("root") or cwd
    if ".." in root.split("/"):
        return False
    try:
        if Path(os.path.realpath(root)) != REPO_ROOT:
            return False
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", match.group("script")],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )
    except (OSError, ValueError):
        return False
    return tracked.returncode == 0


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
