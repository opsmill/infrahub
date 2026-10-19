#!/usr/bin/env python3
"""Ask Claude to start a child session that reviews the pull request a Bash command just opened."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

# Requires gh in command position so a grep or echo that quotes the command does not count.
GH_PR_CREATE = re.compile(r"(?:^|[;&|(`\n]\s*)(?:rtk\s+(?:proxy\s+)?)?gh\s+pr\s+create\b")
PR_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/(\d+)")


def find_opened_pr(payload: dict[str, Any]) -> tuple[str, str] | None:
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return None

    record = (response.get("gitOperation") or {}).get("pr") or {}
    if record.get("action") == "created" and record.get("number") and record.get("url"):
        return str(record["number"]), str(record["url"])

    command = (payload.get("tool_input") or {}).get("command") or ""
    # A failed create chained to a lookup prints the URL of a pull request that already existed.
    if not GH_PR_CREATE.search(command) or "already exists" in (response.get("stderr") or ""):
        return None
    match = PR_URL.search(response.get("stdout") or "")
    if match is None:
        return None
    return match.group(1), match.group(0)


def build_output(number: str, url: str) -> dict[str, Any]:
    review = f"/code-review xhigh {url}"
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT") != "claude-desktop":
        return {"systemMessage": f"PR #{number} opened. To review it, run `{review}` in a new session."}

    instruction = (
        f"Pull request #{number} was just opened ({url}). The user's PR review hook asks you to start its review now "
        "in a child session. Call mcp__ccd_session__start_session (load it with ToolSearch first if it is deferred) "
        f'with initiation "user_asked", context "fresh", use_worktree false, title "Review PR #{number}", '
        f'name "review-pr-{number}", prompt "{review}", and a background saying that the user\'s PR review hook '
        f"started this session to review pull request #{number} right after it was opened, and that the session "
        "reports its findings without changing files, pushing, or posting on GitHub unless the user asks. "
        'If the app refuses to start it, propose the same session with initiation "own_initiative" instead. '
        "Then continue with your current task."
    )
    return {
        "systemMessage": f"PR #{number} opened: starting `{review}` in a child session.",
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": instruction},
    }


def main() -> None:
    opened = find_opened_pr(json.load(sys.stdin))
    if opened is not None:
        print(json.dumps(build_output(*opened)))


if __name__ == "__main__":
    main()
