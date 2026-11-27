from __future__ import annotations

from uuid import uuid4

import pytest
from prefect.client.schemas.objects import StateType

from infrahub.exceptions import ValidationError
from infrahub.graphql.mutations.task import DeliveryRun, TaskRetryDispatcher, TaskRetryHandler
from infrahub.graphql.queries.task_actions import TaskActionGenerator
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, WEBHOOK_SEND
from infrahub.workflows.models import WorkflowInfo


class RecordingRetryHandler(TaskRetryHandler):
    """Records the runs it is asked to retry, for the runs of one workflow."""

    def __init__(self, workflow_name: str) -> None:
        self.workflow_name = workflow_name
        self.submitted = WorkflowInfo(id=uuid4())
        self.retried: list[DeliveryRun] = []

    def supports(self, run: DeliveryRun) -> bool:
        return run.workflow_name == self.workflow_name

    async def retry(self, run: DeliveryRun) -> WorkflowInfo:
        self.retried.append(run)
        return self.submitted


def build_run(workflow_name: str | None, state_type: StateType = StateType.COMPLETED) -> DeliveryRun:
    return DeliveryRun(workflow_name=workflow_name, state_type=state_type, branch_name="main", parameters={})


async def test_retry_goes_to_the_handler_of_the_task_type_only() -> None:
    delivery_handler = RecordingRetryHandler(workflow_name=WEBHOOK_SEND.name)
    artifact_handler = RecordingRetryHandler(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)
    dispatcher = TaskRetryDispatcher(
        action_generator=TaskActionGenerator(), handlers=[delivery_handler, artifact_handler]
    )
    run = build_run(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)

    submitted = await dispatcher.retry(run=run)

    assert submitted == artifact_handler.submitted
    assert artifact_handler.retried == [run]
    assert delivery_handler.retried == []


async def test_retry_that_does_not_apply_to_the_state_of_the_run_reaches_no_handler() -> None:
    artifact_handler = RecordingRetryHandler(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)
    dispatcher = TaskRetryDispatcher(action_generator=TaskActionGenerator(), handlers=[artifact_handler])
    run = build_run(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name, state_type=StateType.RUNNING)

    with pytest.raises(ValidationError, match=r"^Retry is unavailable: Artifact check still in progress\.$"):
        await dispatcher.retry(run=run)

    assert artifact_handler.retried == []


async def test_retry_of_a_retryable_task_type_without_a_handler_is_refused() -> None:
    delivery_handler = RecordingRetryHandler(workflow_name=WEBHOOK_SEND.name)
    dispatcher = TaskRetryDispatcher(action_generator=TaskActionGenerator(), handlers=[delivery_handler])
    run = build_run(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)

    with pytest.raises(ValidationError, match=r"^Retry is unavailable: it is not supported for this task\.$"):
        await dispatcher.retry(run=run)

    assert delivery_handler.retried == []
