#!/usr/bin/env python3
"""Start a `/code-review xhigh` review of a pull request right after a Claude Code or Codex session opens it."""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import shutil
import subprocess  # noqa: S404
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

STATE_DIR = Path.home() / ".cache" / "review-new-pr"
PR_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
# Desktop apps can start hooks with a PATH that leaves out Homebrew and per-user installs.
EXTRA_TOOL_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin"))
# Codex can report a command some time after it finished, so the pull request is looked up for a while.
LOOKUP_ATTEMPTS = 15
LOOKUP_INTERVAL_SECONDS = 6
MAX_PR_AGE_SECONDS = 600
REVIEW_TIMEOUT_SECONDS = 3 * 60 * 60


def find_tool(name: str) -> str | None:
    return shutil.which(name) or shutil.which(name, path=os.pathsep.join(EXTRA_TOOL_DIRS))


def run(args: list[str], cwd: str | None = None, timeout: float = 60) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"{args[0]} did not run: {error}", file=sys.stderr)
        return None


def describe_pr(target: str | None, cwd: str | None) -> dict[str, Any] | None:
    gh = find_tool("gh")
    if gh is None:
        return None
    target_args = [target] if target else []
    result = run([gh, "pr", "view", *target_args, "--json", "number,url,state,createdAt,headRefOid"], cwd=cwd)
    if result is None or result.returncode != 0:
        return None
    return json.loads(result.stdout)


def pinned_commit(pr: dict[str, Any] | None) -> str:
    sha = (pr or {}).get("headRefOid")
    if not sha:
        return ""
    return (
        f"Review it as of commit {sha}: read files with `git show {sha}:<path>` rather than from the working copy, "
        "which the author may still be changing. "
    )


def notify(title: str, message: str) -> None:
    osascript = find_tool("osascript")
    notify_send = find_tool("notify-send")
    if osascript:
        text, heading = json.dumps(message, ensure_ascii=False), json.dumps(title, ensure_ascii=False)
        run([osascript, "-e", f"display notification {text} with title {heading}"])
    elif notify_send:
        run([notify_send, title, message])


def as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_new(pr: dict[str, Any]) -> bool:
    created = calendar.timegm(time.strptime(pr["createdAt"], "%Y-%m-%dT%H:%M:%SZ"))
    return pr.get("state") == "OPEN" and time.time() - created <= MAX_PR_AGE_SECONDS


def claude_hook(payload: dict[str, Any]) -> dict[str, Any] | None:
    record = as_dict(as_dict(as_dict(payload.get("tool_response")).get("gitOperation")).get("pr"))
    if record.get("action") != "created" or not record.get("url"):
        return None

    number, url = record.get("number"), str(record["url"])
    pr = describe_pr(url, payload.get("cwd"))
    # Claude Code also attaches the record to commands that only print a pull request URL, so GitHub has the last word.
    if (pr is not None and not is_new(pr)) or not claim(url):
        return None

    review = f"/code-review xhigh {url}"
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT") != "claude-desktop":
        return {"systemMessage": f"PR #{number} opened. To review it, run `{review}` in a new session."}

    background = (
        f"The user's PR review hook started this session to review pull request #{number} right after it was "
        f"opened. {pinned_commit(pr)}Report the findings without changing files, pushing, or posting on GitHub "
        "unless the user asks."
    )
    instruction = (
        f"Pull request #{number} was just opened ({url}). The user's PR review hook asks you to start its review now "
        "in a child session. Call mcp__ccd_session__start_session (load it with ToolSearch first if it is deferred) "
        f'with initiation "user_asked", context "fresh", use_worktree false, title "Review PR #{number}", '
        f'name "review-pr-{number}", prompt "{review}", and background "{background}" '
        'If the start is refused, propose the same session with initiation "own_initiative" instead. '
        "Then continue with your current task."
    )
    return {
        "systemMessage": f"PR #{number} opened: starting `{review}` in a child session.",
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": instruction},
    }


def start_codex_worker(payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload_file = STATE_DIR / f"payload-{time.time_ns()}.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")
    with (STATE_DIR / "worker.log").open("a", encoding="utf-8") as log:
        subprocess.Popen(  # noqa: S603
            [sys.executable, str(Path(__file__).resolve()), "codex-worker", str(payload_file)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )


def wait_for_new_pr(payload: dict[str, Any]) -> dict[str, Any] | None:
    printed = PR_URL.search(json.dumps(payload.get("tool_response")))
    target = printed.group(0) if printed else None
    for _ in range(LOOKUP_ATTEMPTS):
        pr = describe_pr(target, payload.get("cwd"))
        if pr is not None:
            return pr if is_new(pr) else None
        time.sleep(LOOKUP_INTERVAL_SECONDS)
    return None


def claim(url: str) -> bool:
    claims = STATE_DIR / "claimed"
    claims.mkdir(parents=True, exist_ok=True)
    # Several hooks can fire for the same command at once, so creating this file is the one step that only one wins.
    try:
        os.close(os.open(claims / hashlib.sha256(url.encode()).hexdigest(), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    with (STATE_DIR / "started.txt").open("a", encoding="utf-8") as log:
        log.write(url + "\n")
    return True


def run_review(pr: dict[str, Any], cwd: str | None) -> dict[str, Any] | None:
    claude = find_tool("claude")
    if claude is None:
        return None
    instructions = pinned_commit(pr) + "Report the findings only: do not change files, push, or post on GitHub."
    command = [claude, "-p", f"/code-review xhigh {pr['url']}", "--output-format", "json"]
    command += ["--permission-mode", "auto", "--append-system-prompt", instructions]
    result = run(command, cwd=cwd, timeout=REVIEW_TIMEOUT_SECONDS)
    if result is None or result.returncode != 0:
        print(result.stderr if result else "", file=sys.stderr)
        return None
    try:
        outcome = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(result.stdout, file=sys.stderr)
        return None
    return None if outcome.get("is_error") else outcome


def save_report(pr: dict[str, Any], outcome: dict[str, Any]) -> Path:
    owner, repo = pr["url"].split("/")[3:5]
    report = STATE_DIR / f"{owner}-{repo}-pr-{pr['number']}.md"
    report.write_text(
        f"# Review of {pr['url']}\n\n"
        f"Commit: {pr.get('headRefOid', 'unknown')}\n"
        f"Continue in Claude: claude --desktop --resume {outcome.get('session_id', '')}\n\n"
        f"{outcome.get('result', '')}\n",
        encoding="utf-8",
    )
    return report


def open_in_desktop(pr: dict[str, Any], cwd: str | None) -> None:
    params = {"q": f"/code-review xhigh {pr['url']}"}
    if cwd:
        params["folder"] = cwd
    opener = find_tool("open")
    if opener:
        run([opener, "claude://code/new?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)])
    notify(f"Review PR #{pr['number']}", "The background review did not run. A new Claude session is ready to send.")


def review_in_background(payload_file: Path) -> None:
    payload = as_dict(json.loads(payload_file.read_text(encoding="utf-8")))
    payload_file.unlink()
    pr = wait_for_new_pr(payload)
    if pr is None or not claim(pr["url"]):
        return
    notify(f"Reviewing PR #{pr['number']}", "Claude started /code-review xhigh in the background.")
    outcome = run_review(pr, payload.get("cwd"))
    if outcome is None:
        open_in_desktop(pr, payload.get("cwd"))
        return
    report = save_report(pr, outcome)
    notify(f"Review of PR #{pr['number']} finished", f"Findings saved to {report}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "claude"
    if mode == "codex-worker":
        review_in_background(Path(sys.argv[2]))
        return

    payload = as_dict(json.load(sys.stdin))
    if mode == "codex":
        if "gh pr create" in str(as_dict(payload.get("tool_input")).get("command") or ""):
            start_codex_worker(payload)
        return

    output = claude_hook(payload)
    if output is not None:
        print(json.dumps(output))


if __name__ == "__main__":
    main()
