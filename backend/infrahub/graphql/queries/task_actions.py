from __future__ import annotations

from dataclasses import dataclass

from prefect.client.schemas.objects import TERMINAL_STATES, StateType

from infrahub.exceptions import ValidationError
from infrahub.graphql.types.task import TaskActionType
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
    REQUEST_ARTIFACT_DEFINITION_CHECK,
    WEBHOOK_SEND,
)

RETRY_UNAVAILABLE_REASON = "Delivery still in progress"
CANCEL_UNAVAILABLE_REASON = "Delivery already settled"
CANCEL_IN_PROGRESS_REASON = "Delivery is already being cancelled"
ARTIFACT_CHECK_RETRY_UNAVAILABLE_REASON = "Artifact check still in progress"
UNSUPPORTED_ACTION_REASON = "it is not supported for this task"

ARTIFACT_CHECK_WORKFLOW_NAMES = frozenset(
    {GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name, REQUEST_ARTIFACT_DEFINITION_CHECK.name}
)


@dataclass(frozen=True)
class AvailableAction:
    """A recovery action a task exposes, with whether it currently applies and, if not, why."""

    action: TaskActionType
    available: bool
    unavailability_reason: str | None = None


class TaskActionGenerator:
    """Generates the recovery actions a task run exposes from its workflow and current state.

    A webhook delivery supports retry once it has settled and cancel while it is still in flight. An artifact
    check task supports retry once it has finished, whatever its result, because a failed render also ends in a
    completed run. Any other task type exposes no actions.
    """

    def generate(self, workflow_name: str | None, state_type: StateType | None) -> list[AvailableAction]:
        if workflow_name == WEBHOOK_SEND.name:
            return self._delivery_actions(state_type=state_type)
        if workflow_name in ARTIFACT_CHECK_WORKFLOW_NAMES:
            return self._artifact_check_actions(state_type=state_type)
        return []

    def require_available(
        self, workflow_name: str | None, state_type: StateType | None, action: TaskActionType
    ) -> None:
        """Check that the action applies to a run of this workflow in this state.

        Raises:
            ValidationError: When the task type does not support the action, or the state of the run rules it out.

        """
        actions = self.generate(workflow_name=workflow_name, state_type=state_type)
        searched_action = next((entry for entry in actions if entry.action == action), None)
        if searched_action is None or not searched_action.available:
            reason = searched_action.unavailability_reason if searched_action else UNSUPPORTED_ACTION_REASON
            raise ValidationError(input_value=f"{action.value.capitalize()} is unavailable: {reason}.")

    def _delivery_actions(self, state_type: StateType | None) -> list[AvailableAction]:
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

    def _artifact_check_actions(self, state_type: StateType | None) -> list[AvailableAction]:
        can_retry = state_type in TERMINAL_STATES
        return [
            AvailableAction(
                action=TaskActionType.RETRY,
                available=can_retry,
                unavailability_reason=None if can_retry else ARTIFACT_CHECK_RETRY_UNAVAILABLE_REASON,
            )
        ]
