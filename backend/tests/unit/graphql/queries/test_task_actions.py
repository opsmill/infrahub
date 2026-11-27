from __future__ import annotations

from dataclasses import dataclass

import pytest
from prefect.client.schemas.objects import StateType

from infrahub.graphql.queries.task_actions import (
    ARTIFACT_CHECK_RETRY_UNAVAILABLE_REASON,
    CANCEL_IN_PROGRESS_REASON,
    CANCEL_UNAVAILABLE_REASON,
    RETRY_UNAVAILABLE_REASON,
    AvailableAction,
    TaskActionGenerator,
    TaskActionType,
)
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
    REQUEST_ARTIFACT_DEFINITION_CHECK,
    WEBHOOK_SEND,
)


@dataclass
class AvailableActionsCase:
    name: str
    workflow_name: str | None
    state_type: StateType | None
    expected: list[AvailableAction]


RETRY_AVAILABLE = AvailableAction(action=TaskActionType.RETRY, available=True)
RETRY_BLOCKED = AvailableAction(
    action=TaskActionType.RETRY, available=False, unavailability_reason=RETRY_UNAVAILABLE_REASON
)
CANCEL_AVAILABLE = AvailableAction(action=TaskActionType.CANCEL, available=True)
CANCEL_BLOCKED = AvailableAction(
    action=TaskActionType.CANCEL, available=False, unavailability_reason=CANCEL_UNAVAILABLE_REASON
)
CANCEL_IN_PROGRESS = AvailableAction(
    action=TaskActionType.CANCEL, available=False, unavailability_reason=CANCEL_IN_PROGRESS_REASON
)
ARTIFACT_CHECK_RETRY_BLOCKED = AvailableAction(
    action=TaskActionType.RETRY, available=False, unavailability_reason=ARTIFACT_CHECK_RETRY_UNAVAILABLE_REASON
)


CASES = [
    AvailableActionsCase(
        name="terminal_completed_allows_retry",
        workflow_name=WEBHOOK_SEND.name,
        state_type=StateType.COMPLETED,
        expected=[RETRY_AVAILABLE, CANCEL_BLOCKED],
    ),
    AvailableActionsCase(
        name="terminal_failed_allows_retry",
        workflow_name=WEBHOOK_SEND.name,
        state_type=StateType.FAILED,
        expected=[RETRY_AVAILABLE, CANCEL_BLOCKED],
    ),
    AvailableActionsCase(
        name="terminal_cancelled_allows_retry",
        workflow_name=WEBHOOK_SEND.name,
        state_type=StateType.CANCELLED,
        expected=[RETRY_AVAILABLE, CANCEL_BLOCKED],
    ),
    AvailableActionsCase(
        name="running_allows_cancel",
        workflow_name=WEBHOOK_SEND.name,
        state_type=StateType.RUNNING,
        expected=[RETRY_BLOCKED, CANCEL_AVAILABLE],
    ),
    AvailableActionsCase(
        name="scheduled_allows_cancel",
        workflow_name=WEBHOOK_SEND.name,
        state_type=StateType.SCHEDULED,
        expected=[RETRY_BLOCKED, CANCEL_AVAILABLE],
    ),
    AvailableActionsCase(
        name="cancelling_allows_retry_blocks_cancel",
        workflow_name=WEBHOOK_SEND.name,
        state_type=StateType.CANCELLING,
        expected=[RETRY_AVAILABLE, CANCEL_IN_PROGRESS],
    ),
    AvailableActionsCase(
        name="non_webhook_run_has_no_actions",
        workflow_name="webhook-process",
        state_type=StateType.COMPLETED,
        expected=[],
    ),
    AvailableActionsCase(
        name="unknown_workflow_has_no_actions",
        workflow_name=None,
        state_type=StateType.COMPLETED,
        expected=[],
    ),
    AvailableActionsCase(
        name="artifact_target_check_completed_allows_retry_only",
        workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
        state_type=StateType.COMPLETED,
        expected=[RETRY_AVAILABLE],
    ),
    AvailableActionsCase(
        name="artifact_target_check_failed_allows_retry_only",
        workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
        state_type=StateType.FAILED,
        expected=[RETRY_AVAILABLE],
    ),
    AvailableActionsCase(
        name="artifact_target_check_crashed_allows_retry_only",
        workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
        state_type=StateType.CRASHED,
        expected=[RETRY_AVAILABLE],
    ),
    AvailableActionsCase(
        name="artifact_target_check_cancelled_allows_retry_only",
        workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
        state_type=StateType.CANCELLED,
        expected=[RETRY_AVAILABLE],
    ),
    AvailableActionsCase(
        name="artifact_target_check_running_blocks_retry",
        workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
        state_type=StateType.RUNNING,
        expected=[ARTIFACT_CHECK_RETRY_BLOCKED],
    ),
    AvailableActionsCase(
        name="artifact_target_check_cancelling_blocks_retry",
        workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
        state_type=StateType.CANCELLING,
        expected=[ARTIFACT_CHECK_RETRY_BLOCKED],
    ),
    AvailableActionsCase(
        name="artifact_definition_check_completed_allows_retry_only",
        workflow_name=REQUEST_ARTIFACT_DEFINITION_CHECK.name,
        state_type=StateType.COMPLETED,
        expected=[RETRY_AVAILABLE],
    ),
    AvailableActionsCase(
        name="artifact_definition_check_scheduled_blocks_retry",
        workflow_name=REQUEST_ARTIFACT_DEFINITION_CHECK.name,
        state_type=StateType.SCHEDULED,
        expected=[ARTIFACT_CHECK_RETRY_BLOCKED],
    ),
    AvailableActionsCase(
        name="artifact_check_in_unknown_state_blocks_retry",
        workflow_name=REQUEST_ARTIFACT_DEFINITION_CHECK.name,
        state_type=None,
        expected=[ARTIFACT_CHECK_RETRY_BLOCKED],
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_generate_available_actions(case: AvailableActionsCase) -> None:
    actions = TaskActionGenerator().generate(workflow_name=case.workflow_name, state_type=case.state_type)
    assert actions == case.expected
