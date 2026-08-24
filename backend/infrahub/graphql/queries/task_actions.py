from __future__ import annotations

from dataclasses import dataclass

from prefect.client.schemas.objects import TERMINAL_STATES, StateType

from infrahub.graphql.types.task import TaskActionType
from infrahub.workflows.catalogue import WEBHOOK_SEND

RETRY_UNAVAILABLE_REASON = "Delivery still in progress"
CANCEL_UNAVAILABLE_REASON = "Delivery already settled"
CANCEL_IN_PROGRESS_REASON = "Delivery is already being cancelled"


@dataclass(frozen=True)
class AvailableAction:
    """A recovery action a task exposes, with whether it currently applies and, if not, why."""

    action: TaskActionType
    available: bool
    unavailability_reason: str | None = None


class TaskActionGenerator:
    """Generates the recovery actions a task run exposes from its workflow and current state.

    Only webhook deliveries support actions today: retry once the delivery has settled, cancel while
    it is still in flight. Any other task type exposes no actions.
    """

    def generate(self, workflow_name: str | None, state_type: StateType | None) -> list[AvailableAction]:
        if workflow_name != WEBHOOK_SEND.name:
            return []

        is_terminal = state_type in TERMINAL_STATES
        is_cancelling = state_type == StateType.CANCELLING
        can_retry = is_terminal or is_cancelling
        can_cancel = not is_terminal and not is_cancelling
        if can_cancel:
            cancel_reason = None
        elif is_cancelling:
            cancel_reason = CANCEL_IN_PROGRESS_REASON
        else:
            cancel_reason = CANCEL_UNAVAILABLE_REASON
        return [
            AvailableAction(
                action=TaskActionType.RETRY,
                available=can_retry,
                unavailability_reason=None if can_retry else RETRY_UNAVAILABLE_REASON,
            ),
            AvailableAction(
                action=TaskActionType.CANCEL,
                available=can_cancel,
                unavailability_reason=cancel_reason,
            ),
        ]
