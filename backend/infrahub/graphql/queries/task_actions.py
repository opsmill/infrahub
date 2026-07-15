from __future__ import annotations

from dataclasses import dataclass

from prefect.client.schemas.objects import TERMINAL_STATES, StateType

from infrahub.graphql.types.task import TaskActionType
from infrahub.workflows.catalogue import WEBHOOK_SEND

RETRY_UNAVAILABLE_REASON = "Delivery still in progress"
CANCEL_UNAVAILABLE_REASON = "Delivery already settled"


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
        return [
            AvailableAction(
                action=TaskActionType.RETRY,
                available=is_terminal,
                unavailability_reason=None if is_terminal else RETRY_UNAVAILABLE_REASON,
            ),
            AvailableAction(
                action=TaskActionType.CANCEL,
                available=not is_terminal,
                unavailability_reason=None if not is_terminal else CANCEL_UNAVAILABLE_REASON,
            ),
        ]
