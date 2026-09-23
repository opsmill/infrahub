from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from dependabot_autopilot.checks import CiState
from dependabot_autopilot.decision import (
    ANALYSIS_DEADLINE,
    HOLD_LABEL,
    Action,
    Decision,
    Evidence,
    Settings,
    decide,
    strictest,
)
from dependabot_autopilot.ports import (
    AccountType,
    PullRequest,
    PullRequestState,
    Review,
    ReviewState,
    RunConclusion,
    RunStatus,
    WorkflowRun,
)
from dependabot_autopilot.report import Ecosystem, Impact, PackageFinding, ReportError, Verdict, VerdictReport

HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"
OLD_SHA = "0123456789abcdef0123456789abcdef01234567"
APP_LOGIN = "opsmill-dependabot-autopilot[bot]"
PUSHED_AT = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
NOW = PUSHED_AT + timedelta(minutes=20)
SAFE = Verdict.SAFE_TO_MERGE
REVIEW = Verdict.REVIEW_REQUIRED
NEEDS = Verdict.NEEDS_CODE_CHANGES


def pull_request(
    *,
    state: PullRequestState = PullRequestState.OPEN,
    merged: bool = False,
    labels: tuple[str, ...] = ("dependencies",),
) -> PullRequest:
    return PullRequest(
        number=10689,
        html_url="https://github.com/opsmill/infrahub/pull/10689",
        author_login="dependabot[bot]",
        base_ref="stable",
        head_sha=HEAD_SHA,
        head_repo_full_name="opsmill/infrahub",
        state=state,
        merged=merged,
        labels=labels,
        head_committed_at=PUSHED_AT,
    )


def package(*, name: str = "fastapi", verdict: Verdict = SAFE) -> PackageFinding:
    impacts = (Impact(summary="Signature changed", path="backend/infrahub/server.py", line=12),)
    return PackageFinding(
        name=name,
        ecosystem=Ecosystem.UV,
        from_version="1.0.0",
        to_version="1.1.0",
        verdict=verdict,
        impacts=impacts if verdict is NEEDS else (),
        opportunities=(),
    )


def report(
    *,
    verdict: Verdict = SAFE,
    packages: tuple[PackageFinding, ...] | None = None,
    head_sha: str = HEAD_SHA,
    pr_number: int = 10689,
) -> VerdictReport:
    return VerdictReport(
        pr_number=pr_number,
        head_sha=head_sha,
        verdict=verdict,
        packages=(package(verdict=verdict),) if packages is None else packages,
        report_markdown="## Report",
    )


def analysis_run(
    *,
    status: RunStatus = RunStatus.COMPLETED,
    conclusion: RunConclusion | None = RunConclusion.SUCCESS,
) -> WorkflowRun:
    return WorkflowRun(
        id=42,
        name="dependabot-autopilot-analyze",
        path=".github/workflows/dependabot-autopilot-analyze.lock.yml",
        event="pull_request",
        head_sha=HEAD_SHA,
        status=status,
        conclusion=conclusion,
        created_at=PUSHED_AT + timedelta(seconds=30),
    )


def review(
    *,
    state: ReviewState,
    login: str = "alice",
    author_type: AccountType = AccountType.USER,
    minute: int = 5,
    review_id: int = 1,
) -> Review:
    return Review(
        id=review_id,
        author_login=login,
        author_type=author_type,
        state=state,
        commit_id=HEAD_SHA,
        submitted_at=PUSHED_AT + timedelta(minutes=minute),
    )


DEFAULT_EVIDENCE = Evidence(
    pr=pull_request(),
    report=report(),
    analysis_run=analysis_run(),
    added_packages=(),
    ci_state=CiState.GREEN,
    reviews=(),
    commit_authors=("dependabot[bot]",),
)


def run_decide(*, merge_enabled: bool = True, now: datetime = NOW, **changes: object) -> Decision:
    return decide(
        evidence=dataclasses.replace(DEFAULT_EVIDENCE, **changes),
        settings=Settings(merge_enabled=merge_enabled, app_login=APP_LOGIN),
        now=now,
    )


def test_verdict_strictness_order() -> None:
    assert NEEDS.strictness > REVIEW.strictness > SAFE.strictness
    assert strictest(verdicts=[SAFE, NEEDS, REVIEW]) is NEEDS
    assert strictest(verdicts=[SAFE, REVIEW, SAFE]) is REVIEW
    assert strictest(verdicts=[SAFE]) is SAFE


@pytest.mark.parametrize(
    ("overall", "package_verdicts", "expected"),
    [
        pytest.param(SAFE, (SAFE, SAFE), SAFE, id="all-safe"),
        pytest.param(SAFE, (SAFE, REVIEW), REVIEW, id="package-review-over-safe"),
        pytest.param(SAFE, (REVIEW, NEEDS), NEEDS, id="package-needs-over-review"),
        pytest.param(NEEDS, (SAFE, SAFE), NEEDS, id="overall-stricter-than-packages"),
        pytest.param(REVIEW, (SAFE,), REVIEW, id="overall-review"),
    ],
)
def test_effective_verdict_is_the_strictest_of_packages_and_overall(
    overall: Verdict, package_verdicts: tuple[Verdict, ...], expected: Verdict
) -> None:
    packages = tuple(package(name=f"pkg-{index}", verdict=v) for index, v in enumerate(package_verdicts))

    decision = run_decide(report=report(verdict=overall, packages=packages))

    assert decision.effective_verdict is expected


def test_package_stricter_than_overall_is_a_named_reason() -> None:
    packages = (package(name="fastapi"), package(name="pydantic", verdict=REVIEW))

    decision = run_decide(report=report(verdict=SAFE, packages=packages))

    assert decision.action is Action.REVIEW_REQUIRED
    assert any("pydantic" in reason and "review-required" in reason for reason in decision.reasons)


def test_safe_green_merge_on_without_hold_approves_and_merges() -> None:
    decision = run_decide()

    assert decision == Decision(
        action=Action.APPROVE_AND_MERGE, effective_verdict=SAFE, reasons=(), ci_state=CiState.GREEN
    )


def test_merge_switch_off_is_label_only() -> None:
    decision = run_decide(merge_enabled=False)

    assert decision.action is Action.LABEL_ONLY
    assert decision.effective_verdict is SAFE
    assert any("switched off" in reason for reason in decision.reasons)


def test_needs_code_changes_is_its_own_action() -> None:
    decision = run_decide(report=report(verdict=NEEDS))

    assert decision.action is Action.NEEDS_CODE_CHANGES
    assert decision.effective_verdict is NEEDS


def test_review_required_is_escalated() -> None:
    decision = run_decide(report=report(verdict=REVIEW))

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW


def test_missing_report_after_completed_analysis_is_review_required() -> None:
    decision = run_decide(analysis_run=analysis_run(conclusion=RunConclusion.FAILURE), report=None)

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert any("no verdict report" in reason and "failure" in reason for reason in decision.reasons)


@pytest.mark.parametrize(
    "conclusion", [RunConclusion.FAILURE, RunConclusion.TIMED_OUT, RunConclusion.CANCELLED, RunConclusion.SKIPPED]
)
def test_report_from_an_analysis_run_that_did_not_succeed_is_review_required(conclusion: RunConclusion) -> None:
    decision = run_decide(analysis_run=analysis_run(conclusion=conclusion))

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert "analysis run did not succeed" in decision.reasons


def test_malformed_report_is_review_required_with_its_error() -> None:
    decision = run_decide(report=ReportError("verdict has unknown value 'yolo'"))

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert any("malformed" in reason and "yolo" in reason for reason in decision.reasons)


def test_report_for_another_pull_request_is_review_required() -> None:
    decision = run_decide(report=report(pr_number=1))

    assert decision.action is Action.REVIEW_REQUIRED
    assert any("#1" in reason for reason in decision.reasons)


def test_stale_report_is_review_required() -> None:
    decision = run_decide(report=report(head_sha=OLD_SHA))

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert any("stale" in reason and OLD_SHA[:12] in reason for reason in decision.reasons)


def test_stale_report_while_head_analysis_runs_is_pending() -> None:
    decision = run_decide(
        report=report(head_sha=OLD_SHA), analysis_run=analysis_run(status=RunStatus.IN_PROGRESS, conclusion=None)
    )

    assert decision.action is Action.PENDING
    assert decision.effective_verdict is None


@pytest.mark.parametrize("status", [RunStatus.QUEUED, RunStatus.IN_PROGRESS, RunStatus.REQUESTED])
def test_analysis_still_running_is_pending(status: RunStatus) -> None:
    decision = run_decide(analysis_run=analysis_run(status=status, conclusion=None), report=None)

    assert decision.action is Action.PENDING
    assert decision.effective_verdict is None


def test_no_analysis_run_before_the_deadline_is_pending() -> None:
    decision = run_decide(report=None, analysis_run=None, now=PUSHED_AT + ANALYSIS_DEADLINE - timedelta(seconds=1))

    assert decision.action is Action.PENDING


def test_no_analysis_run_after_the_deadline_is_review_required() -> None:
    assert timedelta(minutes=60) == ANALYSIS_DEADLINE

    decision = run_decide(report=None, analysis_run=None, now=PUSHED_AT + ANALYSIS_DEADLINE)

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert decision.reasons == ("analysis did not run",)


def test_added_lockfile_package_caps_safe_at_review_required() -> None:
    decision = run_decide(added_packages=("annotated-doc", "@biomejs/cli-darwin-arm64"))

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert any("annotated-doc" in reason for reason in decision.reasons)
    assert any("@biomejs/cli-darwin-arm64" in reason for reason in decision.reasons)


def test_added_lockfile_package_does_not_relax_needs_code_changes() -> None:
    decision = run_decide(report=report(verdict=NEEDS), added_packages=("annotated-doc",))

    assert decision.action is Action.NEEDS_CODE_CHANGES


def test_unverified_check_caps_safe_at_review_required() -> None:
    decision = run_decide(unverified=("uv.lock cannot be parsed",))

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert decision.reasons == ("uv.lock cannot be parsed",)


@pytest.mark.parametrize("other_author", ["alice", None], ids=["other-login", "unlinked-author"])
def test_commit_not_authored_by_dependabot_caps_safe_at_review_required(other_author: str | None) -> None:
    decision = run_decide(commit_authors=("dependabot[bot]", other_author))

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert decision.reasons == ("pull request contains commits not authored by dependabot[bot]",)


def test_ci_red_escalates_safe_to_review_required() -> None:
    decision = run_decide(ci_state=CiState.RED)

    assert decision.action is Action.REVIEW_REQUIRED
    assert decision.effective_verdict is REVIEW
    assert decision.ci_state is CiState.RED
    assert any("CI" in reason for reason in decision.reasons)


def test_ci_pending_waits_on_a_safe_verdict() -> None:
    decision = run_decide(ci_state=CiState.PENDING)

    assert decision.action is Action.WAIT_FOR_CI
    assert decision.effective_verdict is SAFE


def test_hold_label_prevents_approve_and_merge() -> None:
    decision = run_decide(pr=pull_request(labels=("dependencies", HOLD_LABEL)))

    assert decision.action is Action.LABEL_ONLY
    assert decision.effective_verdict is SAFE
    assert any(HOLD_LABEL in reason for reason in decision.reasons)


def test_human_change_request_prevents_approve_and_merge() -> None:
    decision = run_decide(reviews=(review(state=ReviewState.CHANGES_REQUESTED),))

    assert decision.action is Action.LABEL_ONLY
    assert any("alice" in reason for reason in decision.reasons)


def test_human_change_request_later_approved_no_longer_blocks() -> None:
    reviews = (
        review(state=ReviewState.CHANGES_REQUESTED, minute=5, review_id=1),
        review(state=ReviewState.COMMENTED, minute=6, review_id=2),
        review(state=ReviewState.APPROVED, minute=7, review_id=3),
    )

    assert run_decide(reviews=reviews).action is Action.APPROVE_AND_MERGE


def test_human_change_request_dismissed_no_longer_blocks() -> None:
    reviews = (
        review(state=ReviewState.CHANGES_REQUESTED, minute=5, review_id=1),
        review(state=ReviewState.DISMISSED, minute=8, review_id=2),
    )

    assert run_decide(reviews=reviews).action is Action.APPROVE_AND_MERGE


@pytest.mark.parametrize(
    ("login", "author_type"),
    [
        (APP_LOGIN, AccountType.BOT),
        ("copilot-pull-request-reviewer[bot]", AccountType.BOT),
        (APP_LOGIN, AccountType.USER),
    ],
)
def test_change_requests_from_the_app_or_bots_are_not_human(login: str, author_type: AccountType) -> None:
    reviews = (review(state=ReviewState.CHANGES_REQUESTED, login=login, author_type=author_type),)

    assert run_decide(reviews=reviews).action is Action.APPROVE_AND_MERGE


def test_hold_does_not_suppress_a_blocking_review() -> None:
    decision = run_decide(pr=pull_request(labels=(HOLD_LABEL,)), report=report(verdict=NEEDS))

    assert decision.action is Action.NEEDS_CODE_CHANGES


@pytest.mark.parametrize(
    "pr",
    [
        pytest.param(pull_request(state=PullRequestState.CLOSED), id="closed"),
        pytest.param(pull_request(state=PullRequestState.CLOSED, merged=True), id="merged"),
        pytest.param(dataclasses.replace(pull_request(), merged=True), id="merged-flag"),
    ],
)
def test_closed_or_merged_pull_request_gets_no_action(pr: PullRequest) -> None:
    decision = run_decide(pr=pr)

    assert decision.action is Action.NONE
    assert decision.effective_verdict is None
