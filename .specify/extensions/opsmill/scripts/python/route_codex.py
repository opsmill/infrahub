#!/usr/bin/env python3
"""Codex PreToolUse hook: run the Spec Kit scripts that need PyYAML through python-run.sh.

Codex has no session environment file, so this hook rewrites each such call to run through
python-run.sh, which points the Spec Kit scripts at the project's Python environment.
Standard library only: it runs with whatever python3 Codex finds.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

# This script is installed at .specify/extensions/opsmill/scripts/python/.
REPO_ROOT = Path(__file__).resolve().parents[5]
WRAPPER = Path(__file__).resolve().parent.parent / "bash" / "python-run.sh"
# Codex runs a rewritten command without asking, so only one exact call of a Spec Kit core script
# that reads preset manifests with PyYAML is accepted, with nothing that the shell could read
# differently.
SCRIPT_CALL = re.compile(
    r"[ \t]*(?:(?:ba)?sh[ \t]+)?"
    r"(?P<quote>['\"]?)(?:(?P<root>/[^'\"$`\\\x00-\x1f\x7f]+)/)?"
    r"\.specify/scripts/bash/(?:setup-plan|setup-tasks|resolve-template|create-new-feature)\.sh(?P=quote)"
    r"(?:[ \t]+[A-Za-z0-9_./:=@+,-]+)*[ \t]*"
)
# Inside quotes, a checkout path may hold spaces and other characters that the shell reads literally there.
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
        return Path(os.path.realpath(root)) == REPO_ROOT
    except (OSError, ValueError):
        return False


def main() -> None:
    hook_input = json.load(sys.stdin)
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command")
    if hook_input.get("tool_name") != "Bash" or not isinstance(command, str):
        return
    if not is_speckit_script_call(command, hook_input.get("cwd") or os.getcwd()):
        return

    updated_command = f"{shlex.quote(str(WRAPPER))} {shlex.quote(command)}"
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
