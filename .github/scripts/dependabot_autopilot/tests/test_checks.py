from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dependabot_autopilot.checks import CiState, evaluate_ci
from dependabot_autopilot.ports import CheckRun, CommitState, CommitStatus, RunConclusion, RunStatus, WorkflowRun

HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"
OWN_WORKFLOWS = frozenset({"dependabot-autopilot-analyze", "dependabot-autopilot-act", "dependabot-autopilot-digest"})
FAILING_CONCLUSIONS = [
    RunConclusion.FAILURE,
    RunConclusion.CANCELLED,
    RunConclusion.TIMED_OUT,
    RunConclusion.ACTION_REQUIRED,
    RunConclusion.STALE,
]
PASSING_CONCLUSIONS = [RunConclusion.SUCCESS, RunConclusion.SKIPPED, RunConclusion.NEUTRAL]
UNFINISHED_STATUSES = [
    RunStatus.REQUESTED,
    RunStatus.QUEUED,
    RunStatus.WAITING,
    RunStatus.PENDING,
    RunStatus.IN_PROGRESS,
]


def workflow_run(
    *,
    name: str = "CI",
    status: RunStatus = RunStatus.COMPLETED,
    conclusion: RunConclusion | None = RunConclusion.SUCCESS,
    run_id: int = 1,
) -> WorkflowRun:
    return WorkflowRun(
        id=run_id,
        name=name,
        path=f".github/workflows/{name.lower()}.yml",
        event="pull_request",
        head_sha=HEAD_SHA,
        status=status,
        conclusion=conclusion,
        created_at=datetime(2026, 9, 23, 9, 0, tzinfo=UTC),
    )


def check_run(
    *,
    app_slug: str = "chromatic-com",
    status: RunStatus = RunStatus.COMPLETED,
    conclusion: RunConclusion | None = RunConclusion.SUCCESS,
) -> CheckRun:
    return CheckRun(id=10, name="UI Tests", app_slug=app_slug, head_sha=HEAD_SHA, status=status, conclusion=conclusion)


def commit_status(*, state: CommitState = CommitState.SUCCESS) -> CommitStatus:
    return CommitStatus(context="ci/external", state=state)


def evaluate(
    *,
    runs: list[WorkflowRun] | None = None,
    check_runs: list[CheckRun] | None = None,
    statuses: list[CommitStatus] | None = None,
) -> CiState:
    return evaluate_ci(
        runs=[workflow_run()] if runs is None else runs,
        check_runs=[check_run()] if check_runs is None else check_runs,
        statuses=[commit_status()] if statuses is None else statuses,
        own_workflows=OWN_WORKFLOWS,
    )


def test_every_source_passing_is_green() -> None:
    assert evaluate() is CiState.GREEN


def test_no_check_runs_and_no_statuses_with_a_passing_ci_run_is_green() -> None:
    assert evaluate(check_runs=[], statuses=[]) is CiState.GREEN


@pytest.mark.parametrize("conclusion", PASSING_CONCLUSIONS)
def test_passing_conclusions_are_green(conclusion: RunConclusion) -> None:
    assert (
        evaluate(
            runs=[workflow_run(), workflow_run(name="Chromatic", conclusion=conclusion, run_id=2)],
            check_runs=[check_run(conclusion=conclusion)],
        )
        is CiState.GREEN
    )


@pytest.mark.parametrize("status", UNFINISHED_STATUSES)
def test_unfinished_workflow_run_is_pending(status: RunStatus) -> None:
    runs = [workflow_run(), workflow_run(name="E2E", status=status, conclusion=None, run_id=2)]

    assert evaluate(runs=runs) is CiState.PENDING


@pytest.mark.parametrize("status", UNFINISHED_STATUSES)
def test_unfinished_check_run_is_pending(status: RunStatus) -> None:
    assert evaluate(check_runs=[check_run(status=status, conclusion=None)]) is CiState.PENDING


def test_pending_commit_status_is_pending() -> None:
    assert evaluate(statuses=[commit_status(state=CommitState.PENDING)]) is CiState.PENDING


def test_no_ci_run_at_all_is_pending() -> None:
    assert evaluate(runs=[]) is CiState.PENDING


def test_only_own_workflow_runs_counts_as_no_ci_run() -> None:
    runs = [workflow_run(name=name, run_id=index) for index, name in enumerate(sorted(OWN_WORKFLOWS))]

    assert evaluate(runs=runs) is CiState.PENDING


@pytest.mark.parametrize("conclusion", FAILING_CONCLUSIONS)
def test_failing_workflow_run_is_red(conclusion: RunConclusion) -> None:
    runs = [workflow_run(), workflow_run(name="E2E", conclusion=conclusion, run_id=2)]

    assert evaluate(runs=runs) is CiState.RED


@pytest.mark.parametrize("conclusion", FAILING_CONCLUSIONS)
def test_failing_check_run_is_red(conclusion: RunConclusion) -> None:
    assert evaluate(check_runs=[check_run(conclusion=conclusion)]) is CiState.RED


@pytest.mark.parametrize("state", [CommitState.FAILURE, CommitState.ERROR])
def test_failing_commit_status_is_red(state: CommitState) -> None:
    assert evaluate(statuses=[commit_status(state=state)]) is CiState.RED


def test_failure_wins_over_pending() -> None:
    runs = [
        workflow_run(conclusion=RunConclusion.FAILURE),
        workflow_run(name="E2E", status=RunStatus.IN_PROGRESS, conclusion=None, run_id=2),
    ]

    assert evaluate(runs=runs) is CiState.RED


def test_own_workflow_runs_are_excluded() -> None:
    runs = [
        workflow_run(),
        workflow_run(name="dependabot-autopilot-act", status=RunStatus.IN_PROGRESS, conclusion=None, run_id=2),
        workflow_run(name="dependabot-autopilot-analyze", conclusion=RunConclusion.FAILURE, run_id=3),
    ]

    assert evaluate(runs=runs) is CiState.GREEN


def test_github_actions_check_runs_are_excluded() -> None:
    check_runs = [
        check_run(),
        check_run(app_slug="github-actions", status=RunStatus.IN_PROGRESS, conclusion=None),
        check_run(app_slug="github-actions", conclusion=RunConclusion.FAILURE),
    ]

    assert evaluate(check_runs=check_runs) is CiState.GREEN
