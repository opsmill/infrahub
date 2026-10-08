from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterState,
    FlowRunFilterStateType,
    FlowRunFilterTags,
)
from prefect.client.schemas.objects import StateType

from infrahub.git.writeback.service import RetryableDeliveryError
from infrahub.workflows.constants import WorkflowTag

if TYPE_CHECKING:
    from prefect import Task
    from prefect.client.schemas.objects import State, TaskRun

    from infrahub.task_manager.flow_run.prefect_client import FlowRunQuerying


def delivery_run_tags(repository_id: str) -> list[str]:
    """Return the tags that a delivery run of the repository carries from its submission.

    A run that waits in the queue has not started, so only the tags of its submission find it.
    """
    return [WorkflowTag.RELATED_NODE.render(identifier=repository_id), WorkflowTag.REPOSITORY_DELIVERY.render()]


def is_retryable_delivery_failure(task: Task[..., Any], task_run: TaskRun, state: State[Any]) -> bool:  # noqa: ARG001
    """Retry a delivery attempt only when it failed in a way that a later attempt can fix."""
    return isinstance(state.data, RetryableDeliveryError)


def next_retry_delay(
    *, run_count: int, retries: int, retry_delay_seconds: float | Sequence[float] | None
) -> timedelta | None:
    """Return the wait before the retry that follows a failure of the attempt, or None when no retry follows.

    The wait is the one that Prefect takes: the delay at the index of the retry in a list, whose last delay
    repeats, or the single delay given.

    Args:
        run_count: The number of the attempt, from 1.

    """
    if run_count > retries:
        return None
    if not retry_delay_seconds:
        return timedelta(0)
    if isinstance(retry_delay_seconds, Sequence):
        return timedelta(seconds=retry_delay_seconds[min(run_count - 1, len(retry_delay_seconds) - 1)])
    return timedelta(seconds=retry_delay_seconds)


class PrefectDeliveryRunQuery:
    """Answer from Prefect whether a delivery run of a repository waits to start."""

    def __init__(self, client: FlowRunQuerying) -> None:
        self.client = client

    async def has_queued_run(self, *, repository_id: str) -> bool:
        # A running run is left out, because its worker can be dead and the lock and the progress time judge it.
        queued = FlowRunFilterStateType(any_=[StateType.SCHEDULED, StateType.PENDING])
        runs = await self.client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                tags=FlowRunFilterTags(all_=delivery_run_tags(repository_id)),
                state=FlowRunFilterState(type=queued),
            ),
            limit=1,
        )
        return bool(runs)
