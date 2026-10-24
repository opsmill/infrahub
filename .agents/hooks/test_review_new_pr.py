"""Tests for the hook that starts a review after a Claude Code or Codex session opens a pull request."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
URL = "https://github.com/opsmill/infrahub/pull/11133"
RECORD = {"pr": {"action": "created", "number": 11133, "url": URL}}
PARALLEL_HOOKS = 4
NOTIFICATIONS_PER_REVIEW = 2

# Stand-ins keep the tests off GitHub, off the Claude API and off the desktop.
FAKE_TOOLS = {
    "gh": (
        '[ "$FAKE_GH" = fail ] && exit 1\n'
        'printf \'{"number":11133,"url":"%s","state":"%s","createdAt":"%s","headRefOid":"abc123"}\' '
        '"$FAKE_URL" "$FAKE_STATE" "$FAKE_CREATED"\n'
    ),
    "claude": (
        'echo "claude $*" >> "$TOOL_LOG"\n'
        '[ "$FAKE_CLAUDE" = fail ] && exit 1\n'
        'printf \'{"session_id":"s-42","result":"Two findings","is_error":false}\'\n'
    ),
    "osascript": 'echo "osascript $*" >> "$TOOL_LOG"\n',
    "open": 'echo "open $*" >> "$TOOL_LOG"\n',
}


def hook_command(settings_file: str) -> str:
    settings = json.loads((REPO_ROOT / settings_file).read_text(encoding="utf-8"))
    return settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]


def created_at(age_seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age_seconds))


def bash_payload(command: str, stdout: str = "", record: object = None) -> dict[str, Any]:
    response: dict[str, Any] = {"stdout": stdout, "stderr": ""}
    if record is not None:
        response["gitOperation"] = record
    return {"cwd": str(REPO_ROOT), "tool_name": "Bash", "tool_input": {"command": command}, "tool_response": response}


def run_claude_hook(env: dict[str, str], payload: object) -> subprocess.CompletedProcess[str]:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    command = ["bash", "-c", hook_command(".claude/settings.json")]
    return subprocess.run(command, input=raw, capture_output=True, text=True, env=env, check=False)


def run_codex_hook(env: dict[str, str], command: str) -> subprocess.CompletedProcess[str]:
    payload = {"cwd": str(REPO_ROOT), "tool_name": "Bash", "tool_input": {"command": command}}
    payload["tool_response"] = {"output": f"{URL}\n"}
    hook = ["sh", "-c", hook_command(".codex/hooks.json")]
    return subprocess.run(
        hook, cwd=REPO_ROOT, input=json.dumps(payload), capture_output=True, text=True, env=env, check=False
    )


def wait_for(condition: Callable[[], bool], timeout: float = 20) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


def tool_calls(env: dict[str, str]) -> str:
    log = Path(env["TOOL_LOG"])
    return log.read_text(encoding="utf-8") if log.exists() else ""


def state_dir(env: dict[str, str]) -> Path:
    return Path(env["HOME"]) / ".cache" / "review-new-pr"


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in FAKE_TOOLS.items():
        tool = bin_dir / name
        tool.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        tool.chmod(0o755)
    return {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TOOL_LOG": str(tmp_path / "tools.log"),
        "CLAUDE_PROJECT_DIR": str(REPO_ROOT),
        "CLAUDE_CODE_ENTRYPOINT": "claude-desktop",
        "FAKE_URL": URL,
        "FAKE_STATE": "OPEN",
        "FAKE_CREATED": created_at(30),
    }


@pytest.mark.parametrize("entrypoint", ["claude-desktop", "cli"])
def test_claude_asks_for_the_review_subagent_with_the_head_commit(env: dict[str, str], entrypoint: str) -> None:
    env["CLAUDE_CODE_ENTRYPOINT"] = entrypoint

    result = run_claude_hook(env, bash_payload("rtk gh pr create --fill", URL, RECORD))

    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert result.returncode == 0
    assert not result.stderr
    assert f"/code-review xhigh {URL}" in output["systemMessage"]
    assert 'subagent_type "pr-reviewer"' in context
    assert f'prompt "Review pull request {URL}. Its head commit is abc123."' in context


@pytest.mark.parametrize(
    ("variable", "value"),
    [("FAKE_CREATED", created_at(900)), ("FAKE_STATE", "CLOSED")],
    ids=["older-than-ten-minutes", "closed"],
)
def test_claude_ignores_a_record_for_a_pull_request_that_is_not_new(
    env: dict[str, str], variable: str, value: str
) -> None:
    env[variable] = value

    result = run_claude_hook(env, bash_payload("python3 script.py", URL, RECORD))

    assert result.returncode == 0
    assert not result.stdout


def test_claude_reviews_each_pull_request_once(env: dict[str, str]) -> None:
    payload = bash_payload("gh pr create --fill", URL, RECORD)

    first, second = run_claude_hook(env, payload), run_claude_hook(env, payload)

    assert first.stdout
    assert not second.stdout


def test_claude_still_asks_when_github_does_not_answer(env: dict[str, str]) -> None:
    env["FAKE_GH"] = "fail"

    result = run_claude_hook(env, bash_payload("gh pr create --fill", URL, RECORD))

    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert f'prompt "Review pull request {URL}."' in context
    assert "head commit" not in context


@pytest.mark.parametrize(
    "payload",
    [
        bash_payload("rtk git push && rtk gh pr create --fill", f"{URL}\n"),
        bash_payload('grep -rn "gh pr create" docs', URL),
        bash_payload("gh pr create --fill", URL, "created"),
        bash_payload("gh pr create --fill", URL, {"pr": [1]}),
        "[1, 2]",
        {"tool_name": "Edit", "tool_input": {}, "tool_response": {"filePath": "/a"}},
    ],
    ids=["no-record", "grep", "record-is-text", "pr-is-a-list", "payload-is-a-list", "other-tool"],
)
def test_claude_ignores_input_without_a_pull_request_record(env: dict[str, str], payload: object) -> None:
    result = run_claude_hook(env, payload)

    assert result.returncode == 0
    assert not result.stdout
    assert not result.stderr


def test_claude_hook_does_nothing_when_the_script_is_missing(env: dict[str, str], tmp_path: Path) -> None:
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)

    result = run_claude_hook(env, bash_payload("gh pr create --fill", URL, RECORD))

    assert result.returncode == 0
    assert not result.stdout


def test_claude_hooks_firing_together_ask_once(env: dict[str, str]) -> None:
    raw = json.dumps(bash_payload("gh pr create --fill", URL, RECORD))
    command = ["bash", "-c", hook_command(".claude/settings.json")]

    hooks = [
        subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        for _ in range(PARALLEL_HOOKS)
    ]
    outputs = [hook.communicate(raw)[0] for hook in hooks]

    assert sum(bool(output.strip()) for output in outputs) == 1


def test_codex_runs_the_review_in_the_background(env: dict[str, str]) -> None:
    result = run_codex_hook(env, "rtk gh pr create --draft --fill")

    report = state_dir(env) / "opsmill-infrahub-pr-11133.md"
    assert result.returncode == 0
    assert not result.stdout
    assert wait_for(lambda: report.exists() and tool_calls(env).count("osascript") == NOTIFICATIONS_PER_REVIEW)
    assert f"claude -p /code-review xhigh {URL}" in tool_calls(env)
    assert "as of commit abc123" in tool_calls(env)
    assert "claude --desktop --resume s-42" in report.read_text(encoding="utf-8")
    assert (state_dir(env) / "started.txt").read_text(encoding="utf-8").split() == [URL]
    assert not list(state_dir(env).glob("payload-*"))


def test_codex_opens_a_desktop_session_when_the_review_fails(env: dict[str, str]) -> None:
    env["FAKE_CLAUDE"] = "fail"

    run_codex_hook(env, "gh pr create --fill")

    assert wait_for(lambda: "open claude://code/new?" in tool_calls(env))
    link = next(line for line in tool_calls(env).splitlines() if line.startswith("open "))
    assert "q=%2Fcode-review%20xhigh%20https%3A%2F%2Fgithub.com%2Fopsmill%2Finfrahub%2Fpull%2F11133" in link
    assert "folder=" in link


def test_codex_ignores_commands_that_do_not_open_a_pull_request(env: dict[str, str]) -> None:
    result = run_codex_hook(env, "ls -la")

    assert result.returncode == 0
    assert not state_dir(env).exists()


def test_codex_ignores_a_pull_request_that_is_not_new(env: dict[str, str]) -> None:
    env["FAKE_CREATED"] = created_at(900)

    run_codex_hook(env, "gh pr create --fill")

    assert wait_for(lambda: state_dir(env).exists() and not list(state_dir(env).glob("payload-*")))
    time.sleep(1)
    assert "claude" not in tool_calls(env)


def test_codex_hooks_firing_together_run_one_review(env: dict[str, str]) -> None:
    for _ in range(PARALLEL_HOOKS):
        run_codex_hook(env, "gh pr create --fill")

    report = state_dir(env) / "opsmill-infrahub-pr-11133.md"
    assert wait_for(lambda: report.exists() and tool_calls(env).count("osascript") == NOTIFICATIONS_PER_REVIEW)
    time.sleep(1)
    assert tool_calls(env).count("claude -p") == 1
