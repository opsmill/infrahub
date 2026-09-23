"""Turn an analysis report and the repository state of a pull request into the action the autopilot takes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from dependabot_autopilot.checks import CiState
from dependabot_autopilot.ports import AccountType, PullRequestState, ReviewState, RunConclusion, RunStatus
from dependabot_autopilot.report import ReportError, Verdict

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import datetime

    from dependabot_autopilot.ports import PullRequest, Review, WorkflowRun
    from dependabot_autopilot.report import VerdictReport

ANALYSIS_DEADLINE = timedelta(minutes=60)
HOLD_LABEL = "autopilot/hold"

_REVIEW_STATES_THAT_SET_A_POSITION = frozenset(
    {ReviewState.APPROVED, ReviewState.CHANGES_REQUESTED, ReviewState.DISMISSED}
)


class Action(StrEnum):
    NONE = "none"
    """The pull request is closed or merged."""
    PENDING = "pending"
    """The analysis of the head commit has not produced a verdict yet."""
    NEEDS_CODE_CHANGES = "needs-code-changes"
    """Submit a blocking review and notify the owners."""
    REVIEW_REQUIRED = "review-required"
    """Label and notify the owners; never approve or merge."""
    WAIT_FOR_CI = "wait-for-ci"
    """Safe to merge, but CI on the head commit has not finished."""
    LABEL_ONLY = "label-only"
    """Safe to merge with CI green, but a human hold or the merge switch keeps it from being merged."""
    APPROVE_AND_MERGE = "approve-and-merge"


@dataclass(frozen=True)
class Decision:
    action: Action
    effective_verdict: Verdict | None
    """`None` while the analysis is pending and for closed or merged pull requests."""
    reasons: tuple[str, ...]
    """Why the effective verdict is stricter than the agent's, or why a safe verdict is not merged."""
    ci_state: CiState


def strictest(*, verdicts: Iterable[Verdict]) -> Verdict:
    return max(verdicts, key=lambda verdict: verdict.strictness)


@dataclass(frozen=True)
class Evidence:
    """Everything observed about the pull request's current head commit."""

    pr: PullRequest
    report: VerdictReport | ReportError | None
    """The verdict report, the error raised while loading it, or `None` when no artifact was found."""
    analysis_run: WorkflowRun | None
    """The latest analysis workflow run for the head commit, if any."""
    added_packages: tuple[str, ...]
    """Package names the pull request's lockfile changes introduce."""
    ci_state: CiState
    reviews: tuple[Review, ...]
    unverified: tuple[str, ...] = ()
    """Checks that could not be completed, each capping the verdict at review-required."""


@dataclass(frozen=True)
class Settings:
    merge_enabled: bool
    app_login: str
    """The autopilot's own login, whose reviews never count as a human's."""


def decide(*, evidence: Evidence, settings: Settings, now: datetime) -> Decision:
    """Decide what to do for the pull request's current head commit."""
    pr, ci_state = evidence.pr, evidence.ci_state
    if pr.merged or pr.state is PullRequestState.CLOSED:
        return Decision(action=Action.NONE, effective_verdict=None, reasons=(), ci_state=ci_state)
    assessment = _assess_report(pr=pr, report=evidence.report, analysis_run=evidence.analysis_run, now=now)
    if assessment is None:
        return Decision(action=Action.PENDING, effective_verdict=None, reasons=(), ci_state=ci_state)
    verdict, reasons = assessment
    if evidence.added_packages:
        verdict = strictest(verdicts=[verdict, Verdict.REVIEW_REQUIRED])
        reasons += tuple(
            f"the lockfile adds `{name}`, a package that was not present before" for name in evidence.added_packages
        )
    if evidence.unverified:
        verdict = strictest(verdicts=[verdict, Verdict.REVIEW_REQUIRED])
        reasons += evidence.unverified
    if ci_state is CiState.RED:
        verdict = strictest(verdicts=[verdict, Verdict.REVIEW_REQUIRED])
        reasons += ("CI failed on the head commit",)
    if verdict is not Verdict.SAFE_TO_MERGE:
        action = Action.NEEDS_CODE_CHANGES if verdict is Verdict.NEEDS_CODE_CHANGES else Action.REVIEW_REQUIRED
        return Decision(action=action, effective_verdict=verdict, reasons=reasons, ci_state=ci_state)
    blockers = _human_holds(pr=pr, reviews=evidence.reviews, app_login=settings.app_login)
    if not settings.merge_enabled:
        blockers += ("automatic merge is switched off",)
    if ci_state is CiState.PENDING:
        action = Action.WAIT_FOR_CI
    elif blockers:
        action = Action.LABEL_ONLY
    else:
        action = Action.APPROVE_AND_MERGE
    return Decision(action=action, effective_verdict=verdict, reasons=reasons + blockers, ci_state=ci_state)


def _assess_report(
    *,
    pr: PullRequest,
    report: VerdictReport | ReportError | None,
    analysis_run: WorkflowRun | None,
    now: datetime,
) -> tuple[Verdict, tuple[str, ...]] | None:
    """Return the verdict the report supports with its downgrade reasons, or `None` while the analysis is pending."""
    if isinstance(report, ReportError):
        return Verdict.REVIEW_REQUIRED, (f"the verdict report is malformed: {report}",)
    if report is None:
        return _assess_missing_report(pr=pr, analysis_run=analysis_run, stale=(), now=now)
    if report.pr_number != pr.number:
        return Verdict.REVIEW_REQUIRED, (
            f"the verdict report is for pull request #{report.pr_number}, not #{pr.number}",
        )
    if report.head_sha == pr.head_sha:
        verdict, reasons = _report_verdict(report=report)
        if _analysis_did_not_succeed(pr=pr, analysis_run=analysis_run):
            return strictest(verdicts=[verdict, Verdict.REVIEW_REQUIRED]), (*reasons, "analysis run did not succeed")
        return verdict, reasons
    stale = f"the verdict report is stale: it analysed {report.head_sha[:12]}, the head is {pr.head_sha[:12]}"
    return _assess_missing_report(pr=pr, analysis_run=analysis_run, stale=(stale,), now=now)


def _assess_missing_report(
    *, pr: PullRequest, analysis_run: WorkflowRun | None, stale: tuple[str, ...], now: datetime
) -> tuple[Verdict, tuple[str, ...]] | None:
    if analysis_run is not None and analysis_run.head_sha == pr.head_sha:
        if analysis_run.status is not RunStatus.COMPLETED:
            return None
        return Verdict.REVIEW_REQUIRED, stale or (
            f"the analysis run finished ({analysis_run.conclusion}) with no verdict report",
        )
    if now - pr.head_committed_at >= ANALYSIS_DEADLINE:
        return Verdict.REVIEW_REQUIRED, (*stale, "analysis did not run")
    return None


def _analysis_did_not_succeed(*, pr: PullRequest, analysis_run: WorkflowRun | None) -> bool:
    return (
        analysis_run is not None
        and analysis_run.head_sha == pr.head_sha
        and analysis_run.status is RunStatus.COMPLETED
        and analysis_run.conclusion is not RunConclusion.SUCCESS
    )


def _report_verdict(*, report: VerdictReport) -> tuple[Verdict, tuple[str, ...]]:
    verdict = strictest(verdicts=[report.verdict, *(package.verdict for package in report.packages)])
    reasons = tuple(
        f"`{package.name}` is {package.verdict}, stricter than the overall verdict {report.verdict}"
        for package in report.packages
        if package.verdict.strictness > report.verdict.strictness
    )
    return verdict, reasons


def _human_holds(*, pr: PullRequest, reviews: Sequence[Review], app_login: str) -> tuple[str, ...]:
    holds = [f"the `{HOLD_LABEL}` label is set"] if HOLD_LABEL in pr.labels else []
    position: dict[str, ReviewState] = {}
    for review in sorted(reviews, key=lambda review: review.id):
        is_human = review.author_type is not AccountType.BOT and review.author_login != app_login
        if is_human and review.state in _REVIEW_STATES_THAT_SET_A_POSITION:
            position[review.author_login] = review.state
    holds.extend(
        f"{login} requested changes"
        for login, state in sorted(position.items())
        if state is ReviewState.CHANGES_REQUESTED
    )
    return tuple(holds)
