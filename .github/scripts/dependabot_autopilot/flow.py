"""Apply the autopilot's decision for a Dependabot pull request through the GitHub port."""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from dependabot_autopilot.checks import evaluate_ci
from dependabot_autopilot.codeowners import owners_for
from dependabot_autopilot.decision import DEPENDABOT_LOGIN, Action, Decision, Evidence, Settings, decide
from dependabot_autopilot.lockfiles import LockfileError, added_packages
from dependabot_autopilot.ports import FileStatus, GitHubError, PullRequestState, ReviewEvent, ReviewState, RunStatus
from dependabot_autopilot.report import (
    REPORT_FILENAME,
    ReportError,
    Verdict,
    VerdictReport,
    load_report,
    neutralize_untrusted,
    sanitize_report_markdown,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from dependabot_autopilot.ports import ChangedFile, GitHubPort, PullRequest, Review, WorkflowRun

MARKER = "<!-- dependabot-autopilot -->"
BASE_BRANCH = "stable"
ANALYSIS_WORKFLOW = "dependabot-autopilot-analyze"
ANALYSIS_WORKFLOW_PATH = ".github/workflows/dependabot-autopilot-analyze.lock.yml"
ANALYSIS_EVENT = "pull_request"
ACT_WORKFLOW = "dependabot-autopilot-act"
VERDICT_ARTIFACT = "dependabot-autopilot-verdict"
CODEOWNERS_PATH = ".github/CODEOWNERS"
LOCKFILE_NAMES = frozenset({"uv.lock", "pnpm-lock.yaml", "package-lock.json"})
VERDICT_LABELS = {
    Verdict.SAFE_TO_MERGE: "autopilot/safe",
    Verdict.NEEDS_CODE_CHANGES: "autopilot/needs-code-changes",
    Verdict.REVIEW_REQUIRED: "autopilot/review-required",
}

_REQUESTED_FOR = re.compile(r"^<!-- dependabot-autopilot:requested-for ([0-9a-f]{40}) -->$", flags=re.MULTILINE)
_ACTIONS_NOTIFYING_OWNERS = frozenset({Action.NEEDS_CODE_CHANGES, Action.REVIEW_REQUIRED})
_ACTION_SUMMARIES = {
    Action.PENDING: "waiting for the analysis of the head commit",
    Action.NEEDS_CODE_CHANGES: "blocked until the code is adapted; owners notified",
    Action.REVIEW_REQUIRED: "escalated to the owners",
    Action.WAIT_FOR_CI: "waiting for CI on the head commit",
    Action.LABEL_ONLY: "safe, not merged automatically",
    Action.APPROVE_AND_MERGE: "approved and merged",
}


@dataclass(frozen=True)
class Config:
    repo: str
    app_login: str
    merge_enabled: bool
    fallback_reviewer: str
    """Team slug, `org/team` or `@org/team`; empty when no fallback is configured."""


@dataclass(frozen=True)
class SuppliedReport:
    """A verdict artifact already downloaded from the analysis run that triggered this evaluation."""

    directory: Path
    run_head_sha: str


def is_eligible(*, pr: PullRequest, repo: str) -> bool:
    return pr.author_login == DEPENDABOT_LOGIN and pr.base_ref == BASE_BRANCH and pr.head_repo_full_name == repo


def invalidate(*, github: GitHubPort, config: Config, pr_number: int) -> None:
    """Dismiss the autopilot's approvals given to any commit other than the current head."""
    pr = github.get_pull_request(number=pr_number)
    if not _is_actionable(pr=pr, config=config):
        return
    target = _Target(github=github, config=config, pr=pr, reviews=tuple(github.list_reviews(pr_number=pr_number)))
    _dismiss_approvals(target=target, include_head=False)


def evaluate(
    *, github: GitHubPort, config: Config, pr_number: int, now: datetime, supplied: SuppliedReport | None = None
) -> Decision | None:
    """Decide and apply the action for the pull request's head; `None` when the pull request is out of scope."""
    pr = github.get_pull_request(number=pr_number)
    if not _is_actionable(pr=pr, config=config):
        return None
    runs = github.list_workflow_runs(head_sha=pr.head_sha)
    analysis_run = _latest_analysis_run(runs=runs, head_sha=pr.head_sha)
    report = _resolve_report(github=github, pr=pr, analysis_run=analysis_run, supplied=supplied)
    changed_files = github.list_changed_files(pr_number=pr.number)
    packages, unverified = _added_packages(github=github, pr=pr, changed_files=changed_files)
    ci_state = evaluate_ci(
        runs=runs,
        check_runs=github.list_check_runs(sha=pr.head_sha),
        statuses=github.list_commit_statuses(sha=pr.head_sha),
        own_workflows=(ANALYSIS_WORKFLOW, ACT_WORKFLOW),
    )
    reviews = tuple(github.list_reviews(pr_number=pr.number))
    decision = decide(
        evidence=Evidence(
            pr=pr,
            report=report,
            analysis_run=analysis_run,
            added_packages=packages,
            ci_state=ci_state,
            reviews=reviews,
            commit_authors=tuple(github.list_commit_authors(pr_number=pr.number)),
            unverified=unverified,
        ),
        settings=Settings(merge_enabled=config.merge_enabled, app_login=config.app_login),
        now=now,
    )
    _apply(
        target=_Target(github=github, config=config, pr=pr, reviews=reviews),
        decision=decision,
        report=report if isinstance(report, VerdictReport) else None,
        changed_paths=[changed.path for changed in changed_files],
    )
    return decision


def sweep(*, github: GitHubPort, config: Config, now: datetime, run_url: str) -> bool:
    """Evaluate every open Dependabot pull request; return whether all of them were evaluated without error."""
    succeeded = True
    for summary in github.list_open_pull_requests(base=BASE_BRANCH):
        if summary.author_login != DEPENDABOT_LOGIN or summary.head_repo_full_name != config.repo:
            continue
        # One pull request failing must not stop the sweep of the others; each failure is reported and escalated.
        try:
            evaluate(github=github, config=config, pr_number=summary.number, now=now)
        except Exception as exc:
            succeeded = False
            print(f"evaluation of #{summary.number} failed: {exc!r}", file=sys.stderr)
            escalate(github=github, config=config, pr_number=summary.number, run_url=run_url)
    return succeeded


def escalate(*, github: GitHubPort, config: Config, pr_number: int, run_url: str) -> None:
    """Mark the pull request review-required after the autopilot itself failed, linking the failed run."""
    pr = github.get_pull_request(number=pr_number)
    if not _is_actionable(pr=pr, config=config):
        return
    _set_verdict_label(github=github, pr=pr, verdict=Verdict.REVIEW_REQUIRED)
    current = github.find_marker_comment(pr_number=pr.number, marker=MARKER, author_login=config.app_login)
    body = "\n".join(
        [
            MARKER,
            *_requested_for_lines(current=current),
            "### Dependency-bump autopilot",
            "",
            f"The autopilot failed while evaluating `{pr.head_sha}`: {run_url}",
            "",
            f"**Verdict**: `{Verdict.REVIEW_REQUIRED}`",
        ]
    )
    if body != current:
        github.upsert_marker_comment(pr_number=pr.number, marker=MARKER, body=body, author_login=config.app_login)


def _is_actionable(*, pr: PullRequest, config: Config) -> bool:
    return is_eligible(pr=pr, repo=config.repo) and pr.state is PullRequestState.OPEN and not pr.merged


def _latest_analysis_run(*, runs: Sequence[WorkflowRun], head_sha: str) -> WorkflowRun | None:
    candidates = [
        run
        for run in runs
        if run.name == ANALYSIS_WORKFLOW
        and run.path == ANALYSIS_WORKFLOW_PATH
        and run.event == ANALYSIS_EVENT
        and run.head_sha == head_sha
    ]
    return max(candidates, key=lambda run: (run.created_at, run.id), default=None)


def _resolve_report(
    *, github: GitHubPort, pr: PullRequest, analysis_run: WorkflowRun | None, supplied: SuppliedReport | None
) -> VerdictReport | ReportError | None:
    if supplied is not None and supplied.run_head_sha == pr.head_sha:
        return _load_supplied(supplied=supplied)
    if analysis_run is None or analysis_run.status is not RunStatus.COMPLETED:
        return None
    destination = Path(tempfile.mkdtemp(prefix="dependabot-autopilot-verdict-"))
    downloaded = github.download_artifact(run_id=analysis_run.id, name=VERDICT_ARTIFACT, destination=destination)
    if downloaded is None:
        return None
    return _load(directory=downloaded)


def _load_supplied(*, supplied: SuppliedReport) -> VerdictReport | ReportError | None:
    report = _load(directory=supplied.directory)
    if isinstance(report, VerdictReport) and report.head_sha != supplied.run_head_sha:
        return ReportError(
            f"the report claims {report.head_sha[:12]} but the analysis run was for {supplied.run_head_sha[:12]}"
        )
    return report


def _load(*, directory: Path) -> VerdictReport | ReportError | None:
    candidate = directory / REPORT_FILENAME
    if not candidate.exists() and not candidate.is_symlink():
        return None
    try:
        return load_report(directory=directory)
    except ReportError as exc:
        return exc


def _added_packages(
    *, github: GitHubPort, pr: PullRequest, changed_files: Sequence[ChangedFile]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the package names the lockfile changes add, and a reason for each lockfile that could not be read."""
    names: set[str] = set()
    unverified: list[str] = []
    for changed in changed_files:
        if PurePosixPath(changed.path).name not in LOCKFILE_NAMES or changed.status is FileStatus.REMOVED:
            continue
        try:
            names.update(
                added_packages(
                    path=changed.path,
                    base_text=github.read_file(path=changed.previous_path or changed.path, ref=pr.base_ref),
                    head_text=github.read_file(path=changed.path, ref=pr.head_sha),
                )
            )
        except LockfileError as exc:
            unverified.append(f"new packages could not be checked: {exc}")
    return tuple(sorted(names)), tuple(unverified)


@dataclass(frozen=True)
class _Target:
    github: GitHubPort
    config: Config
    pr: PullRequest
    reviews: tuple[Review, ...]


def _apply(*, target: _Target, decision: Decision, report: VerdictReport | None, changed_paths: Sequence[str]) -> None:
    github, config, pr = target.github, target.config, target.pr
    if decision.action is Action.NONE:
        return
    current = github.find_marker_comment(pr_number=pr.number, marker=MARKER, author_login=config.app_login)
    requested_for = _requested_for(current=current)
    notes: list[str] = []
    if decision.action in _ACTIONS_NOTIFYING_OWNERS:
        _dismiss_approvals(target=target, include_head=True)
        owners = _owners(github=github, pr=pr, changed_paths=changed_paths, fallback=config.fallback_reviewer)
        if owners:
            notes.append(f"**Owners**: {' '.join(owners)}")
        if requested_for != pr.head_sha and _request_reviews(github=github, pr=pr, owners=owners):
            requested_for = pr.head_sha
    else:
        _dismiss_approvals(target=target, include_head=False)
    _set_verdict_label(github=github, pr=pr, verdict=decision.effective_verdict)
    if decision.action is Action.NEEDS_CODE_CHANGES and report is not None:
        _submit_once(target=target, event=ReviewEvent.REQUEST_CHANGES, body=_blocking_review_body(report=report))
    if decision.action is Action.APPROVE_AND_MERGE and report is not None:
        _submit_once(
            target=target,
            event=ReviewEvent.APPROVE,
            body=f"Approved by the dependency-bump autopilot for `{report.head_sha}`.",
        )
        try:
            github.merge(pr_number=pr.number, head_sha=report.head_sha)
        except GitHubError as exc:
            notes.append(f"**Merge attempt failed**, retried on the next run: {_one_line(text=str(exc))}")
    body = _comment_body(pr=pr, decision=decision, report=report, requested_for=requested_for, notes=notes)
    if body != current:
        github.upsert_marker_comment(pr_number=pr.number, marker=MARKER, body=body, author_login=config.app_login)


def _dismiss_approvals(*, target: _Target, include_head: bool) -> None:
    pr = target.pr
    for review in target.reviews:
        if review.author_login != target.config.app_login or review.state is not ReviewState.APPROVED:
            continue
        if review.commit_id == pr.head_sha and not include_head:
            continue
        target.github.dismiss_review(
            pr_number=pr.number,
            review_id=review.id,
            message=f"The dependency-bump autopilot has not approved the head commit `{pr.head_sha}`.",
        )


def _submit_once(*, target: _Target, event: ReviewEvent, body: str) -> None:
    pr = target.pr
    state = ReviewState.APPROVED if event is ReviewEvent.APPROVE else ReviewState.CHANGES_REQUESTED
    already_submitted = any(
        review.author_login == target.config.app_login and review.commit_id == pr.head_sha and review.state is state
        for review in target.reviews
    )
    if not already_submitted:
        target.github.submit_review(pr_number=pr.number, event=event, body=body, commit_id=pr.head_sha)


def _set_verdict_label(*, github: GitHubPort, pr: PullRequest, verdict: Verdict | None) -> None:
    verdict_labels = set(VERDICT_LABELS.values())
    desired = [label for label in pr.labels if label not in verdict_labels]
    if verdict is not None:
        desired.append(VERDICT_LABELS[verdict])
    if sorted(desired) != sorted(pr.labels):
        github.set_labels(pr_number=pr.number, labels=desired)


def _owners(*, github: GitHubPort, pr: PullRequest, changed_paths: Sequence[str], fallback: str) -> tuple[str, ...]:
    codeowners_text = github.read_file(path=CODEOWNERS_PATH, ref=pr.base_ref) or ""
    fallback_owner = _fallback_owner(value=fallback)
    owners = owners_for(paths=changed_paths, codeowners_text=codeowners_text, fallback=fallback_owner)
    return tuple(owner for owner in owners if owner)


def _fallback_owner(*, value: str) -> str:
    slug = value.strip().removeprefix("@")
    if not slug:
        return ""
    return f"@{slug}" if "/" in slug else f"@opsmill/{slug}"


def _request_reviews(*, github: GitHubPort, pr: PullRequest, owners: Sequence[str]) -> bool:
    """Request reviews from the owners; return whether the request was made."""
    teams = [owner.split("/", 1)[1] for owner in owners if owner.startswith("@") and "/" in owner]
    users = [owner.removeprefix("@") for owner in owners if owner.startswith("@") and "/" not in owner]
    if not teams and not users:
        return False
    try:
        github.request_reviewers(pr_number=pr.number, users=users, teams=teams)
    except GitHubError as exc:
        print(f"requesting reviews on #{pr.number} failed, retrying on the next run: {exc}", file=sys.stderr)
        return False
    return True


def _requested_for(*, current: str | None) -> str | None:
    match = None if current is None else _REQUESTED_FOR.search(current)
    return None if match is None else match.group(1)


def _requested_for_lines(*, current: str | None) -> list[str]:
    sha = _requested_for(current=current)
    return [] if sha is None else [f"<!-- dependabot-autopilot:requested-for {sha} -->"]


def _blocking_review_body(*, report: VerdictReport) -> str:
    lines = ["The dependency-bump autopilot found code that must change before this bump can merge:", ""]
    lines.extend(
        f"- `{_one_line(text=impact.path)}:{impact.line}` — {_one_line(text=impact.summary)}"
        for package in report.packages
        for impact in package.impacts
    )
    return "\n".join(lines)


def _comment_body(
    *,
    pr: PullRequest,
    decision: Decision,
    report: VerdictReport | None,
    requested_for: str | None,
    notes: Sequence[str],
) -> str:
    verdict = "pending" if decision.effective_verdict is None else str(decision.effective_verdict)
    lines = [MARKER]
    if requested_for is not None:
        lines.append(f"<!-- dependabot-autopilot:requested-for {requested_for} -->")
    lines.extend(
        [
            "### Dependency-bump autopilot",
            "",
            "| | |",
            "|---|---|",
            f"| Analysed head | `{pr.head_sha}` |",
            f"| Verdict | `{verdict}` |",
            f"| CI | `{decision.ci_state}` |",
            f"| Action | {_ACTION_SUMMARIES[decision.action]} |",
        ]
    )
    if decision.reasons:
        lines.extend(["", "**Reasons**", ""])
        lines.extend(f"- {_one_line(text=reason)}" for reason in decision.reasons)
    for note in notes:
        lines.extend(["", note])
    if report is not None:
        lines.extend(["", sanitize_report_markdown(text=report.report_markdown)])
    return "\n".join(lines)


def _one_line(*, text: str) -> str:
    return " ".join(neutralize_untrusted(text=text).split())
