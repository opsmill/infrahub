#!/usr/bin/env python3
"""Run an Infrahub pull request's bug pipeline in the sandbox repository and check how its steps connect.

The slash-command workflows always run from the default branch, so the script resets the sandbox's
`stable` to the pull request's merge commit, keeps only the bug-pipeline workflows, adds a planted bug,
opens an issue for it, and posts each command as the person running it. After each run it checks that:

- the run succeeded and its agent job ran;
- the step's marker reached the issue or pull request, inside a code span;
- the review started by itself and reviewed the latest commit;
- the agent read comments through the MCP gateway, and the gateway hid none of them.

It does not judge the quality of the analysis, the test or the fix.

Only stdlib (Python 3.11 or later) and the `gh` CLI, logged in with write access on the sandbox and the
`workflow` scope. The lock-file check also needs the `gh aw` extension at the version the lock files name.

Usage:
  sandbox_run.py run --pr NUMBER [--resume-issue NUMBER] [--skip-lock-check] [--report FILE]
  sandbox_run.py cleanup

Exit status: 0 when every step passed, 1 when a check failed, 2 when the agents need a decision from a person.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess  # noqa: S404
import sys
import tempfile
import time
from dataclasses import dataclass, field
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

SANDBOX = "opsmill/infrahub-pipeline-sandbox"
SANDBOX_URL = f"https://github.com/{SANDBOX}"
SANDBOX_GIT_URL = f"{SANDBOX_URL}.git"
SANDBOX_BRANCH = "stable"
UPSTREAM = "opsmill/infrahub"
UPSTREAM_URL = f"https://github.com/{UPSTREAM}.git"
BOT_LOGIN = "opsmill-bug-pipeline[bot]"
BUG_LABEL = "type/bug"

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_PATH = f".agents/skills/{SKILL_DIR.name}"
PLANTED_SOURCE = SKILL_DIR / "fixture" / "sandbox_pagination.py"
# The issue text names this path, so change both together.
PLANTED_DIR = "backend/infrahub"
PLANTED_NAME = "sandbox_pagination.py"
ISSUE_BODY = SKILL_DIR / "fixture" / "issue.md"
ISSUE_TITLE = "count_pages returns one page too few"
# Hidden in the issue body so a later run closes only the issues this script opened.
RUN_MARKER = "<!-- bug-pipeline-sandbox-test -->"
PIPELINE_BRANCH_PREFIX = "ai-bug-pipeline-"
# A plain "pull request N" instead of a link, so each run does not add a cross-reference to the upstream pull request.
TESTED_COMMIT_MESSAGE = "Test infrahub pull request {number} at {sha}"
TESTED_COMMIT_RE = re.compile(r"Test infrahub pull request (\d+) at ([0-9a-f]{40})")

LOCK_SOURCES = ("bug-agent-analyst", "bug-agent-test", "bug-agent-fix", "bug-agent-review")
KEPT_WORKFLOWS = frozenset(f"{name}.lock.yml" for name in LOCK_SOURCES)
COMPILER_VERSION_RE = re.compile(r'"compiler_version":"(v[^"]+)"')

MAX_TEST_REVISIONS = 2
MAX_FIX_REVISIONS = 1
# The reviewer hands the pull request to a person instead of reviewing a fourth time in the same mode.
REVIEW_ITERATION_LIMIT = 3
MAX_STEPS = 2 + 2 * REVIEW_ITERATION_LIMIT * 2

POLL_SECONDS = 30
MERGEABILITY_ATTEMPTS = 10
MERGEABILITY_WAIT_SECONDS = 5
GH_ATTEMPTS = 3
RUN_START_TIMEOUT = dt.timedelta(minutes=5)
REVIEW_TIMEOUT = dt.timedelta(minutes=45)
# A workflow's time limit covers only its agent job; queueing and the jobs around it need room as well.
RUN_TIMEOUT_MARGIN = dt.timedelta(minutes=15)
# Comment and run timestamps come from different GitHub services.
CLOCK_SKEW = dt.timedelta(seconds=10)
ACTIVE_RUN_STATUSES = ("queued", "in_progress", "waiting", "pending", "requested")

ANALYSIS_MARKER = "AGENT_ANALYSIS_COMPLETE"
TEST_MARKER = "AGENT_TEST_COMPLETE"
FIX_MARKER = "AGENT_FIX_COMPLETE"
VERDICT_MARKER = "AGENT_REVIEW_VERDICT"
VERDICT_RE = re.compile(
    r"AGENT_REVIEW_VERDICT: (TEST_APPROVED|TEST_CHANGES_REQUESTED|FIX_APPROVED|FIX_CHANGES_REQUESTED)"
)
REVIEWED_SHA_RE = re.compile(r"AGENT_REVIEW_SHA: ([0-9a-f]{40})")
ITERATION_RE = re.compile(r"AGENT_REVIEW_ITERATION: ((?:test|fix)-\d+)")

GATEWAY_LOG = "mcp-gateway.log"
GATEWAY_CALL = "github→tools/call"
GATEWAY_COMMENT_READ = '"method":"get_comments"'
GATEWAY_DIFF_READ = '"method":"get_diff"'
GATEWAY_HIDDEN_DIFF = "pull-request-content"
# The gateway names an item this way when it cannot tell which item a call asked for, such as a number sent as text.
GATEWAY_UNIDENTIFIED = "#unknown"
GATEWAY_LABEL_LINE = "[difc]"
GATEWAY_FILTERED = "[DIFC-FILTERED] "


@dataclass(frozen=True)
class Workflow:
    file: str
    command: str
    timeout: dt.timedelta


ANALYST = Workflow("bug-agent-analyst.lock.yml", "/bug-analyze", dt.timedelta(minutes=40))
TEST_WRITER = Workflow("bug-agent-test.lock.yml", "/bug-tdd", dt.timedelta(minutes=60))
FIXER = Workflow("bug-agent-fix.lock.yml", "/bug-fix", dt.timedelta(minutes=60))
COMMANDS = {workflow.command: workflow for workflow in (ANALYST, TEST_WRITER, FIXER)}
REVIEWER_FILE = "bug-agent-review.lock.yml"


class CheckFailedError(Exception):
    pass


class NeedsPersonError(Exception):
    pass


class GhError(Exception):
    pass


@dataclass
class StepResult:
    name: str
    run_id: int
    run_url: str
    minutes: float
    notes: list[str] = field(default_factory=list)
    failure: str | None = None


@dataclass
class Session:
    pr_number: int
    login: str = ""
    head_sha: str = ""
    issue: int | None = None
    steps: list[StepResult] = field(default_factory=list)


@dataclass(frozen=True)
class Verdict:
    value: str
    reviewed_sha: str | None
    iteration: str | None
    body: str
    posted: dt.datetime


@dataclass
class PipelineState:
    analysis_done: bool
    pull_request: dict[str, Any] | None
    verdict: str | None
    test_change_requests: int
    fix_change_requests: int


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def gh(*args: str, stdin: str | None = None, cwd: Path | None = None, retry: bool = True) -> str:
    attempt = 1
    while True:
        result = subprocess.run(["gh", *args], input=stdin, cwd=cwd, capture_output=True, text=True, check=False)  # noqa: S603, S607
        if result.returncode == 0:
            return result.stdout
        # GitHub sometimes answers with a 5xx while busy, and a retry gets through; a write may have landed anyway.
        if not retry or "HTTP 5" not in result.stderr or attempt >= GH_ATTEMPTS:
            raise GhError(f"gh {' '.join(args)}: {result.stderr.strip()}")
        attempt += 1
        time.sleep(POLL_SECONDS)


def gh_dict(*args: str) -> dict[str, Any]:
    return json.loads(gh(*args))


def gh_list(*args: str) -> list[dict[str, Any]]:
    return json.loads(gh(*args))


def api(path: str, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    if body is None:
        return json.loads(gh("api", "--method", method, path, retry=method == "GET"))
    return json.loads(gh("api", "--method", method, path, "--input", "-", stdin=json.dumps(body), retry=False))


def api_list(path: str) -> list[dict[str, Any]]:
    pages = json.loads(gh("api", "--paginate", "--slurp", path))
    return [item for page in pages for item in page]


def git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False)  # noqa: S603, S607
    if result.returncode != 0:
        raise CheckFailedError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def unescape(text: str) -> str:
    # gh-aw escapes underscores outside code spans when it posts agent output.
    return text.replace("\\_", "_")


def check_access() -> str:
    if not api(f"repos/{SANDBOX}").get("permissions", {}).get("push"):
        raise CheckFailedError(f"Your gh login has no write access on {SANDBOX}, which posting slash commands needs.")
    head, _, body = gh("api", "--include", "user").partition("\n\n")
    scopes = next(
        (line.split(":", 1)[1] for line in head.splitlines() if line.lower().startswith("x-oauth-scopes:")), None
    )
    # Fine-grained and app tokens report no scopes, so only a classic token can be checked here.
    if scopes is not None and "workflow" not in scopes:
        raise CheckFailedError(
            "Your gh token lacks the workflow scope, which resetting the sandbox's workflow files needs. "
            "Run: gh auth refresh -s workflow"
        )
    return json.loads(body)["login"]


def pull_request_commits(pr_number: int) -> tuple[str, str]:
    for _ in range(MERGEABILITY_ATTEMPTS):
        pr = api(f"repos/{UPSTREAM}/pulls/{pr_number}")
        if pr["state"] != "open":
            raise CheckFailedError(f"Pull request {pr_number} is {pr['state']}.")
        if pr["mergeable"] is not None:
            break
        time.sleep(MERGEABILITY_WAIT_SECONDS)
    else:
        raise CheckFailedError(f"GitHub has not yet computed whether pull request {pr_number} can merge; try again.")
    if not pr["mergeable"] or not pr["merge_commit_sha"]:
        raise CheckFailedError(
            f"Pull request {pr_number} conflicts with {pr['base']['ref']}, so GitHub has no merge commit to test. "
            "Rebase it first."
        )
    return pr["head"]["sha"], pr["merge_commit_sha"]


def repository_root() -> Path:
    return Path(git("rev-parse", "--show-toplevel", cwd=SKILL_DIR).strip())


def fetch_merge_commit(root: Path, pr_number: int, head_sha: str, merge_sha: str) -> None:
    git("fetch", "--quiet", UPSTREAM_URL, f"pull/{pr_number}/merge", cwd=root)
    if git("rev-parse", "FETCH_HEAD", cwd=root).strip() != merge_sha:
        raise CheckFailedError(f"GitHub rebuilt the merge commit for pull request {pr_number} meanwhile; try again.")
    if head_sha not in git("rev-list", "--parents", "--max-count=1", merge_sha, cwd=root).split()[1:]:
        raise CheckFailedError(f"GitHub's merge commit for pull request {pr_number} is older than its head; try again.")


def check_lock_files(root: Path, head_sha: str) -> None:
    lock_paths = [f".github/workflows/{name}.lock.yml" for name in LOCK_SOURCES]
    with tempfile.TemporaryDirectory() as tmp:
        checkout = Path(tmp) / "checkout"
        git("worktree", "add", "--quiet", "--detach", str(checkout), head_sha, cwd=root)
        try:
            version = compiler_version(checkout, lock_paths)
            log(f"Recompiling the bug-pipeline workflows with gh-aw {version}")
            gh("aw", "compile", *LOCK_SOURCES, cwd=checkout)
            changed = git("diff", "--name-only", "--", *lock_paths, cwd=checkout).split()
        finally:
            git("worktree", "remove", "--force", str(checkout), cwd=root)
    if changed:
        raise CheckFailedError(
            f"These lock files do not match their .md sources: {', '.join(changed)}. "
            f"Run `gh aw compile {' '.join(LOCK_SOURCES)}` and push the result."
        )


def compiler_version(checkout: Path, lock_paths: Sequence[str]) -> str:
    versions = set()
    for path in lock_paths:
        found = COMPILER_VERSION_RE.search((checkout / path).read_text(encoding="utf-8"))
        if found is None:
            raise CheckFailedError(f"{path} names no gh-aw compiler version.")
        versions.add(found.group(1))
    if len(versions) > 1:
        raise CheckFailedError(f"The lock files name different gh-aw versions: {', '.join(sorted(versions))}.")
    version = versions.pop()
    try:
        installed = gh("aw", "version")
    except GhError as error:
        raise CheckFailedError(f"The gh aw extension is not installed ({error}).") from error
    if version not in installed.split():
        raise CheckFailedError(
            f"The lock files were compiled with gh-aw {version}, but `gh aw version` says {installed.strip()}. "
            f"Install it with: gh extension remove gh-aw && gh extension install github/gh-aw --pin {version}"
        )
    return version


def reset_sandbox(root: Path, pr_number: int, head_sha: str, merge_sha: str, login: str) -> None:
    workflows = set(git("ls-tree", "--name-only", f"{merge_sha}:.github/workflows", cwd=root).split())
    if missing := KEPT_WORKFLOWS - workflows:
        raise CheckFailedError(f"The pull request has no {', '.join(sorted(missing))}.")
    planted_path = f"{PLANTED_DIR}/{PLANTED_NAME}"
    if git("ls-tree", "--name-only", merge_sha, "--", planted_path, cwd=root).strip():
        raise CheckFailedError(f"{planted_path} now exists upstream; give the planted file another name.")
    removed = [
        f".github/workflows/{name}" for name in sorted(workflows - KEPT_WORKFLOWS) if name.endswith((".yml", ".yaml"))
    ]
    with tempfile.TemporaryDirectory() as tmp:
        # A separate index builds the commit without touching the checkout, its index or its hooks.
        index_env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git("read-tree", merge_sha, cwd=root, env=index_env)
        # The agents must not find this skill's description of the planted bug, or a second copy of it.
        removed += git("ls-tree", "-r", "--name-only", merge_sha, "--", SKILL_PATH, cwd=root).split()
        git("update-index", "--force-remove", "--", *removed, cwd=root, env=index_env)
        blob = git("hash-object", "-w", str(PLANTED_SOURCE), cwd=root).strip()
        git("update-index", "--add", "--cacheinfo", f"100644,{blob},{planted_path}", cwd=root, env=index_env)
        tree = git("write-tree", cwd=root, env=index_env).strip()
    email = f"{login}@users.noreply.github.com"
    identity = {**os.environ, "GIT_AUTHOR_NAME": login, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": login}
    identity["GIT_COMMITTER_EMAIL"] = email
    message = TESTED_COMMIT_MESSAGE.format(number=pr_number, sha=head_sha)
    message += (
        "\n\nKeeps only the bug-pipeline workflows, removes the sandbox test's own skill and adds the planted bug."
    )
    commit = git("commit-tree", tree, "-p", merge_sha, "-m", message, cwd=root, env=identity).strip()
    # A push, unlike the API, carries objects the fork network has not shared with the sandbox yet.
    git("push", "--force", "--quiet", SANDBOX_GIT_URL, f"{commit}:refs/heads/{SANDBOX_BRANCH}", cwd=root)
    log(f"Reset the sandbox's {SANDBOX_BRANCH} to {commit[:10]} (pull request {pr_number} at {head_sha[:10]})")


def tested_pull_request() -> tuple[int, str]:
    message = api(f"repos/{SANDBOX}/commits/{SANDBOX_BRANCH}")["commit"]["message"]
    found = TESTED_COMMIT_RE.search(message)
    if found is None:
        raise CheckFailedError(f"This script did not set up the sandbox's {SANDBOX_BRANCH}; start a new run instead.")
    return int(found.group(1)), found.group(2)


def cancel_active_runs() -> None:
    for status in ACTIVE_RUN_STATUSES:
        fields = "databaseId,workflowName"
        for run in gh_list("run", "list", "-R", SANDBOX, "--status", status, "--limit", "50", "--json", fields):
            log(f"Cancelling sandbox run {run['databaseId']} ({run['workflowName']})")
            try:
                gh("run", "cancel", str(run["databaseId"]), "-R", SANDBOX)
            except GhError as error:
                log(f"Could not cancel run {run['databaseId']}, which may have finished: {error}")


def script_issues() -> list[dict[str, Any]]:
    issues = api_list(f"repos/{SANDBOX}/issues?state=open&per_page=100")
    return [issue for issue in issues if "pull_request" not in issue and RUN_MARKER in (issue.get("body") or "")]


def pipeline_pull_requests(issue: int) -> list[dict[str, Any]]:
    fields = "number,url,headRefName,headRefOid,body"
    pull_requests = gh_list("pr", "list", "-R", SANDBOX, "--state", "open", "--limit", "100", "--json", fields)
    return [pr for pr in pull_requests if pr["headRefName"].startswith(f"{PIPELINE_BRANCH_PREFIX}{issue}-")]


def cleanup() -> None:
    issues = script_issues()
    if not issues:
        log("No open sandbox test issues")
    for issue in issues:
        for pr in pipeline_pull_requests(issue["number"]):
            log(f"Closing {pr['url']} and deleting its branch")
            gh("pr", "close", str(pr["number"]), "-R", SANDBOX, "--delete-branch")
        log(f"Closing {issue['html_url']}")
        gh("issue", "close", str(issue["number"]), "-R", SANDBOX)


def open_issue() -> int:
    body = f"{ISSUE_BODY.read_text(encoding='utf-8').rstrip()}\n\n{RUN_MARKER}\n"
    issue = api(f"repos/{SANDBOX}/issues", "POST", {"title": ISSUE_TITLE, "body": body, "labels": [BUG_LABEL]})
    log(f"Opened {issue['html_url']}")
    return issue["number"]


def comments(number: int) -> list[dict[str, Any]]:
    return api_list(f"repos/{SANDBOX}/issues/{number}/comments?per_page=100")


def bot_comments(number: int) -> list[dict[str, Any]]:
    return [comment for comment in comments(number) if comment["user"]["login"] == BOT_LOGIN]


def verdicts(pr_number: int) -> list[Verdict]:
    found = []
    for comment in bot_comments(pr_number):
        body = unescape(comment["body"])
        if (verdict := VERDICT_RE.search(body)) is None:
            continue
        reviewed, iteration = REVIEWED_SHA_RE.search(body), ITERATION_RE.search(body)
        found.append(
            Verdict(
                value=verdict.group(1),
                reviewed_sha=reviewed.group(1) if reviewed else None,
                iteration=iteration.group(1) if iteration else None,
                body=comment["body"],
                posted=parse_time(comment["created_at"]),
            )
        )
    return found


def verdict_for(reviews: list[Verdict], head_sha: str) -> Verdict | None:
    return next((review for review in reversed(reviews) if review.reviewed_sha == head_sha), None)


def read_state(issue: int) -> PipelineState:
    analysis_done = any(ANALYSIS_MARKER in unescape(comment["body"]) for comment in bot_comments(issue))
    pull_requests = pipeline_pull_requests(issue)
    pr = pull_requests[0] if pull_requests else None
    reviews = verdicts(pr["number"]) if pr else []
    current = verdict_for(reviews, pr["headRefOid"]) if pr else None
    return PipelineState(
        analysis_done=analysis_done,
        pull_request=pr,
        verdict=current.value if current else None,
        test_change_requests=sum(review.value == "TEST_CHANGES_REQUESTED" for review in reviews),
        fix_change_requests=sum(review.value == "FIX_CHANGES_REQUESTED" for review in reviews),
    )


def find_command_run(workflow_file: str, *, actor: str, created_after: dt.datetime) -> int:
    # Every comment starts every workflow, so the agents' own comments start runs that skip; only the command's run
    # is started by the person who posted it.
    return find_run(
        workflow_file,
        "issue_comment",
        lambda run: (
            run["triggering_actor"]["login"] == actor and parse_time(run["created_at"]) >= created_after - CLOCK_SKEW
        ),
        pick=min,
    )


def find_review_run(head_sha: str) -> int:
    return find_run(REVIEWER_FILE, "pull_request", lambda run: run["head_sha"] == head_sha, pick=max)


def find_run(
    workflow_file: str,
    event: str,
    matches: Callable[[dict[str, Any]], bool],
    *,
    pick: Callable[..., dict[str, Any]],
) -> int:
    deadline = now() + RUN_START_TIMEOUT
    while True:
        runs = api(f"repos/{SANDBOX}/actions/workflows/{workflow_file}/runs?event={event}&per_page=20")["workflow_runs"]
        if found := [run for run in runs if matches(run)]:
            return pick(found, key=itemgetter("created_at"))["id"]
        if now() > deadline:
            raise CheckFailedError(f"No {workflow_file} run started within {RUN_START_TIMEOUT}.")
        time.sleep(POLL_SECONDS)


def wait_for_run(run_id: int, timeout: dt.timedelta) -> dict[str, Any]:
    deadline = now() + timeout + RUN_TIMEOUT_MARGIN
    fields = "status,conclusion,jobs,createdAt,updatedAt,url"
    while True:
        run = gh_dict("run", "view", str(run_id), "-R", SANDBOX, "--json", fields)
        if run["status"] == "completed":
            return run
        if now() > deadline:
            raise CheckFailedError(f"Run {run['url']} did not finish in time.")
        time.sleep(POLL_SECONDS)


def failure_messages(run: dict[str, Any]) -> str:
    messages = [
        f"{job['name']}: {annotation['message']}"
        for job in run["jobs"]
        if job["conclusion"] == "failure"
        for annotation in api_list(f"repos/{SANDBOX}/check-runs/{job['databaseId']}/annotations")
        if annotation["annotation_level"] == "failure"
    ]
    return " ".join(messages)


def check_run(run: dict[str, Any]) -> None:
    agent = next((job for job in run["jobs"] if job["name"] == "agent"), None)
    if agent is None or agent["conclusion"] == "skipped":
        raise CheckFailedError(
            "The run's agent job did not run. For a command, check that the commenter has write access on the "
            "sandbox; for a review, read the review-gate job."
        )
    if run["conclusion"] != "success":
        raise CheckFailedError(f"The run ended {run['conclusion']}. {failure_messages(run)}".strip())


def hidden_items(lines: list[str]) -> list[str]:
    items = []
    for line in lines:
        if GATEWAY_FILTERED not in line:
            continue
        raw = line.split(GATEWAY_FILTERED, 1)[1]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        description = parsed.get("description") if isinstance(parsed, dict) else None
        items.append(description if isinstance(description, str) else raw)
    return items


def check_gateway(run_id: int, *, needs_comment_reads: bool) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            gh("run", "download", str(run_id), "-R", SANDBOX, "--name", "agent", "--dir", tmp)
        except GhError as error:
            raise CheckFailedError(f"Cannot verify comment access: the run has no agent artifact ({error}).") from error
        logs = sorted(Path(tmp).rglob(GATEWAY_LOG))
        if not logs:
            raise CheckFailedError(f"Cannot verify comment access: the agent artifact has no {GATEWAY_LOG}.")
        lines = logs[0].read_text(encoding="utf-8", errors="replace").splitlines()
    return gateway_notes(lines, needs_comment_reads=needs_comment_reads)


def gateway_notes(lines: list[str], *, needs_comment_reads: bool) -> list[str]:
    if not any(GATEWAY_LABEL_LINE in line for line in lines):
        raise CheckFailedError(f"Cannot verify comment access: {GATEWAY_LOG} has no {GATEWAY_LABEL_LINE} lines.")
    reads = sum(GATEWAY_CALL in line and GATEWAY_COMMENT_READ in line for line in lines)
    diff_reads = sum(GATEWAY_CALL in line and GATEWAY_DIFF_READ in line for line in lines)
    hidden = hidden_items(lines)
    if hidden_comments := [item for item in hidden if "comment" in item.lower()]:
        raise CheckFailedError(f"The MCP gateway hid comments from the agent: {', '.join(hidden_comments)}.")
    hidden_diffs = hidden.count(GATEWAY_HIDDEN_DIFF)
    if hidden_diffs > diff_reads:
        raise CheckFailedError(
            f"The MCP gateway hid {GATEWAY_HIDDEN_DIFF} {hidden_diffs} times but the agent asked for the diff only "
            f"{diff_reads} times, so it also hid the pull request itself."
        )
    unidentified = [item for item in hidden if item.endswith(GATEWAY_UNIDENTIFIED)]
    if others := [item for item in hidden if item != GATEWAY_HIDDEN_DIFF and item not in unidentified]:
        raise CheckFailedError(f"The MCP gateway hid content the agent may need: {', '.join(others)}.")
    if needs_comment_reads and reads == 0:
        raise CheckFailedError(
            f"The agent read no comments through the MCP gateway, so it did not see the earlier steps' output, "
            f"or the format of {GATEWAY_LOG} changed."
        )
    notes = [f"comment reads: {reads}, none hidden"]
    if hidden_diffs:
        notes.append(
            f"warning: the gateway hid the pull request diff on {hidden_diffs} of {diff_reads} requests, "
            "so the agent read it from git"
        )
    notes += [f"warning: the gateway hid {item}; check that the agent asked again and got it" for item in unidentified]
    return notes


def marker_note(text: str, marker: str) -> str:
    if marker in text:
        return f"{marker} present"
    if marker in unescape(text):
        raise CheckFailedError(
            f"{marker} was posted with escaped underscores, which a gate that matches the exact text cannot find; "
            "the agent wrote it outside a code span."
        )
    raise CheckFailedError(f"{marker} is missing.")


def record_step(
    session: Session, name: str, run_id: int, timeout: dt.timedelta, checks: Callable[[int], list[str]]
) -> None:
    log(f"{name}: waiting for run {run_id}")
    run = wait_for_run(run_id, timeout)
    minutes = (parse_time(run["updatedAt"]) - parse_time(run["createdAt"])).total_seconds() / 60
    step = StepResult(name=name, run_id=run_id, run_url=run["url"], minutes=minutes)
    session.steps.append(step)
    try:
        check_run(run)
        step.notes += checks(run_id)
    except (CheckFailedError, GhError) as error:
        step.failure = str(error)
        raise
    log(f"{name}: passed ({'; '.join(step.notes)})")


def record_command_run(
    session: Session, name: str, workflow: Workflow, run_id: int, after_run: Callable[[], list[str]]
) -> None:
    def checks(finished_run_id: int) -> list[str]:
        return [*check_gateway(finished_run_id, needs_comment_reads=workflow != ANALYST), *after_run()]

    record_step(session, name, run_id, workflow.timeout, checks)


def run_command(
    session: Session, name: str, workflow: Workflow, target: int, after_run: Callable[[], list[str]]
) -> None:
    log(f"{name}: posting {workflow.command} on #{target}")
    comment = api(f"repos/{SANDBOX}/issues/{target}/comments", "POST", {"body": workflow.command})
    run_id = find_command_run(workflow.file, actor=session.login, created_after=parse_time(comment["created_at"]))
    record_command_run(session, name, workflow, run_id, after_run)


def analysis_checks(issue: int) -> Callable[[], list[str]]:
    def after_run() -> list[str]:
        for comment in bot_comments(issue):
            if ANALYSIS_MARKER in unescape(comment["body"]):
                return [marker_note(comment["body"], ANALYSIS_MARKER)]
        raise CheckFailedError(
            f"No comment from the pipeline bot contains {ANALYSIS_MARKER}: the analyst did not confirm the bug. "
            "Read its comment on the issue."
        )

    return after_run


def test_pull_request_checks(issue: int) -> Callable[[], list[str]]:
    def after_run() -> list[str]:
        pull_requests = pipeline_pull_requests(issue)
        if not pull_requests:
            raise CheckFailedError(f"No pull request from a {PIPELINE_BRANCH_PREFIX}{issue}- branch was opened.")
        return [f"opened {pull_requests[0]['url']}", marker_note(pull_requests[0]["body"], TEST_MARKER)]

    return after_run


def push_checks(pr_number: int, old_head: str | None, workflow: Workflow) -> Callable[[], list[str]]:
    def after_run() -> list[str]:
        current = gh_dict("pr", "view", str(pr_number), "-R", SANDBOX, "--json", "headRefOid,body")
        if current["headRefOid"] == old_head:
            raise CheckFailedError("The agent pushed no commit, so no review will start.")
        notes = [f"pushed {current['headRefOid'][:10]}"]
        if workflow == FIXER:
            notes.append(marker_note(current["body"], FIX_MARKER))
        return notes

    return after_run


def review(session: Session, pr: dict[str, Any]) -> None:
    head_sha = pr["headRefOid"]
    name = "Review of the fix" if FIX_MARKER in unescape(pr["body"]) else "Review of the test"
    log(f"{name}: looking for the review run of {head_sha[:10]}")
    run_id = find_review_run(head_sha)

    def checks(finished_run_id: int) -> list[str]:
        notes = check_gateway(finished_run_id, needs_comment_reads=True)
        current = verdict_for(verdicts(pr["number"]), head_sha)
        if current is None:
            raise CheckFailedError(f"The review finished but posted no verdict for {head_sha[:10]}.")
        notes.insert(0, f"{current.value} ({current.iteration or 'no iteration marker'})")
        return [*notes, marker_note(current.body, VERDICT_MARKER)]

    record_step(session, name, run_id, REVIEW_TIMEOUT, checks)


def check_command_posted_by_hand(session: Session, issue: int) -> None:
    pull_requests = pipeline_pull_requests(issue)
    pr = pull_requests[0] if pull_requests else None
    posted = [
        (parse_time(comment["created_at"]), target, COMMANDS[comment["body"].strip()])
        for target in [issue, *([pr["number"]] if pr else [])]
        for comment in comments(target)
        if comment["user"]["login"] == session.login and comment["body"].strip() in COMMANDS
    ]
    reviews = verdicts(pr["number"]) if pr else []
    if not posted:
        return
    when, target, workflow = max(posted, key=itemgetter(0))
    if reviews and reviews[-1].posted > when:
        return
    if workflow == ANALYST:
        after_run = analysis_checks(issue)
    elif target == issue:
        after_run = test_pull_request_checks(issue)
    else:
        after_run = push_checks(target, reviews[-1].reviewed_sha if reviews else None, workflow)
    run_id = find_command_run(workflow.file, actor=session.login, created_after=when)
    record_command_run(session, f"{workflow.command}, checked on resume", workflow, run_id, after_run)


def ask_person(session: Session, pr: dict[str, Any], requests: int, workflow: Workflow) -> NeedsPersonError:
    if requests >= REVIEW_ITERATION_LIMIT:
        return NeedsPersonError(
            f"The reviewer asked for changes {requests} times on {pr['url']}, its own limit, so it will not review "
            "again. Read its reviews to decide whether the pipeline change caused this, then run `cleanup`."
        )
    return NeedsPersonError(
        f"The reviewer asked for changes {requests} times on {pr['url']}. Read its last review, then either post "
        f"{workflow.command} on the pull request yourself and continue with "
        f"`run --pr {session.pr_number} --resume-issue {session.issue}`, or run `cleanup`."
    )


def drive(session: Session, issue: int) -> None:
    for _ in range(MAX_STEPS):
        state = read_state(issue)
        pr = state.pull_request
        if not state.analysis_done:
            run_command(session, "Analysis", ANALYST, issue, analysis_checks(issue))
        elif pr is None:
            run_command(session, "Failing test", TEST_WRITER, issue, test_pull_request_checks(issue))
        elif state.verdict is None:
            review(session, pr)
        elif state.verdict == "TEST_CHANGES_REQUESTED":
            if state.test_change_requests > MAX_TEST_REVISIONS:
                raise ask_person(session, pr, state.test_change_requests, TEST_WRITER)
            name = f"Test revision {state.test_change_requests}"
            run_command(
                session, name, TEST_WRITER, pr["number"], push_checks(pr["number"], pr["headRefOid"], TEST_WRITER)
            )
        elif state.verdict == "TEST_APPROVED":
            run_command(session, "Fix", FIXER, pr["number"], push_checks(pr["number"], pr["headRefOid"], FIXER))
        elif state.verdict == "FIX_CHANGES_REQUESTED":
            if state.fix_change_requests > MAX_FIX_REVISIONS:
                raise ask_person(session, pr, state.fix_change_requests, FIXER)
            name = f"Fix revision {state.fix_change_requests}"
            run_command(session, name, FIXER, pr["number"], push_checks(pr["number"], pr["headRefOid"], FIXER))
        else:
            return
    raise CheckFailedError(f"The pipeline did not reach FIX_APPROVED within {MAX_STEPS} steps.")


def table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_report(session: Session, outcome: str) -> str:
    lines = [f"Sandbox run of the bug pipeline at `{session.head_sha[:10]}`: {table_cell(outcome)}", ""]
    if session.issue is not None:
        lines.append(f"- Sandbox issue: {SANDBOX_URL}/issues/{session.issue}")
        try:
            lines += [f"- Sandbox pull request: {pr['url']}" for pr in pipeline_pull_requests(session.issue)]
        except GhError as error:
            log(f"Could not list the sandbox pull requests: {error}")
    lines += ["", "| Step | Run | Minutes | Result | Notes |", "| --- | --- | --- | --- | --- |"]
    for step in session.steps:
        result = "passed" if step.failure is None else f"failed: {step.failure}"
        notes = "; ".join(step.notes)
        lines.append(
            f"| {step.name} | [{step.run_id}]({step.run_url}) | {step.minutes:.0f} | {table_cell(result)} | {table_cell(notes)} |"
        )
    return "\n".join(lines) + "\n"


def start_or_resume(session: Session, args: argparse.Namespace) -> int:
    session.login = check_access()
    if args.resume_issue is not None:
        tested_number, session.head_sha = tested_pull_request()
        if tested_number != args.pr:
            raise CheckFailedError(f"The sandbox is set up for pull request {tested_number}, not {args.pr}.")
        check_command_posted_by_hand(session, args.resume_issue)
        return args.resume_issue
    session.head_sha, merge_sha = pull_request_commits(args.pr)
    root = repository_root()
    fetch_merge_commit(root, args.pr, session.head_sha, merge_sha)
    if not args.skip_lock_check:
        check_lock_files(root, session.head_sha)
    cleanup()
    cancel_active_runs()
    reset_sandbox(root, args.pr, session.head_sha, merge_sha, session.login)
    return open_issue()


def run(args: argparse.Namespace) -> int:
    session = Session(pr_number=args.pr)
    outcome, status = "passed", 0
    try:
        if args.resume_issue is not None:
            session.issue = args.resume_issue
        session.issue = start_or_resume(session, args)
        drive(session, session.issue)
        if not session.steps:
            raise CheckFailedError(
                "This run checked no step, because the pipeline had already finished; use the report of the run "
                "that checked it."
            )
    except (CheckFailedError, GhError) as error:
        outcome, status = f"failed: {error}", 1
    except NeedsPersonError as error:
        outcome, status = f"stopped for a decision: {error}", 2
    log(outcome)
    report = render_report(session, outcome)
    print(report)
    if args.report is not None:
        args.report.write_text(report, encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="Reset the sandbox to a pull request and run its bug pipeline")
    run_parser.add_argument("--pr", type=int, required=True, help="Infrahub pull request number")
    run_parser.add_argument(
        "--resume-issue", type=int, help="Continue an earlier run on this sandbox issue, after posting a command"
    )
    run_parser.add_argument("--skip-lock-check", action="store_true", help="Do not recompile the lock files first")
    run_parser.add_argument("--report", type=Path, help="Also write the Markdown report to this file")
    commands.add_parser("cleanup", help="Close the issues and pull requests that earlier runs left open")
    args = parser.parse_args()
    if args.command == "cleanup":
        cleanup()
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
