#!/usr/bin/env python3
"""Route Codex calls to Spec Kit's YAML-dependent scripts through the venv wrapper."""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


SPECKIT_COMMAND = re.compile(
    r"(?:^|[\s;&|])['\"]?(?:[^\s;&|]*?/)?\.specify/scripts/bash/"
    r"(?:setup-plan|setup-tasks)\.sh(?=$|[\s;&|])"
)


def main() -> None:
    hook_input = json.load(sys.stdin)
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command")
    if hook_input.get("tool_name") != "Bash" or not isinstance(command, str):
        return
    if not SPECKIT_COMMAND.search(command):
        return

    cwd = hook_input.get("cwd") or os.getcwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    wrapper = Path(result.stdout.strip()) / ".agents/hooks/speckit-python-run.sh"
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
