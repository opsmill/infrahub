"""Classify every CI signal on a commit into one green, pending or red state."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from dependabot_autopilot.ports import CommitState, RunConclusion, RunStatus

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from dependabot_autopilot.ports import CheckRun, CommitStatus, WorkflowRun

ACTIONS_APP_SLUG = "github-actions"

_PASSING_CONCLUSIONS = frozenset({RunConclusion.SUCCESS, RunConclusion.SKIPPED, RunConclusion.NEUTRAL})
_PASSING_STATES = frozenset({CommitState.SUCCESS})
_PENDING_STATES = frozenset({CommitState.PENDING})


class CiState(StrEnum):
    GREEN = "green"
    PENDING = "pending"
    RED = "red"


def evaluate_ci(
    *,
    runs: Sequence[WorkflowRun],
    check_runs: Sequence[CheckRun],
    statuses: Sequence[CommitStatus],
    own_workflows: Collection[str],
) -> CiState:
    """Return red on any failure, else pending while anything runs or no CI workflow has started, else green.

    Workflow runs named in `own_workflows` and check runs created by GitHub Actions are ignored; the latter
    duplicate the workflow runs, whose names are what identify the autopilot's own jobs.
    """
    ci_runs = [run for run in runs if run.name not in own_workflows]
    external_check_runs = [check for check in check_runs if check.app_slug != ACTIONS_APP_SLUG]
    states = [
        *(_run_state(status=run.status, conclusion=run.conclusion) for run in ci_runs),
        *(_run_state(status=check.status, conclusion=check.conclusion) for check in external_check_runs),
        *(_status_state(state=status.state) for status in statuses),
    ]
    if CiState.RED in states:
        return CiState.RED
    if not ci_runs or CiState.PENDING in states:
        return CiState.PENDING
    return CiState.GREEN


def _run_state(*, status: RunStatus, conclusion: RunConclusion | None) -> CiState:
    if status is not RunStatus.COMPLETED or conclusion is None:
        return CiState.PENDING
    return CiState.GREEN if conclusion in _PASSING_CONCLUSIONS else CiState.RED


def _status_state(*, state: CommitState) -> CiState:
    if state in _PASSING_STATES:
        return CiState.GREEN
    if state in _PENDING_STATES:
        return CiState.PENDING
    return CiState.RED
