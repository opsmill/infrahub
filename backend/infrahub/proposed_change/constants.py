from __future__ import annotations

from infrahub.exceptions import ValidationError
from infrahub.utils import InfrahubStringEnum


class ProposedChangeApprovalDecision(InfrahubStringEnum):
    APPROVE = "approve"
    CANCEL_APPROVE = "cancel-approve"
    REJECT = "reject"
    CANCEL_REJECT = "cancel-reject"


class ProposedChangeState(InfrahubStringEnum):
    OPEN = "open"
    MERGED = "merged"
    MERGING = "merging"
    CLOSED = "closed"
    CANCELED = "canceled"

    @property
    def is_completed(self) -> bool:
        """Check if the proposed change is in a completed state."""
        return self != ProposedChangeState.OPEN

    def validate_state_check_run(self) -> None:
        if self == ProposedChangeState.OPEN:
            return

        raise ValidationError(input_value="Unable to trigger check on proposed changes that aren't in the open state")

    def validate_updatable(self) -> None:
        if self.is_completed:
            raise ValidationError(
                input_value=f"A proposed change in the {self.value} state is not allowed to be updated"
            )

    def validate_reviewable(self) -> None:
        if self.is_completed:
            raise ValidationError(
                input_value=f"A proposed change in the {self.value} state is not allowed to be reviewed"
            )

    def validate_state_transition(self, updated_state: ProposedChangeState) -> None:
        if self == ProposedChangeState.OPEN:
            return

        if self == ProposedChangeState.CLOSED and updated_state not in [
            ProposedChangeState.CANCELED,
            ProposedChangeState.OPEN,
        ]:
            raise ValidationError(
                input_value="A closed proposed change is only allowed to transition to the open state"
            )


class ProposedChangeAction(InfrahubStringEnum):
    OPEN = "open"
    CLOSE = "close"
    SET_DRAFT = "set-draft"
    UNSET_DRAFT = "unset-draft"
    MERGE = "merge"
    APPROVE = "approve"
    CANCEL_APPROVE = "cancel-approve"
    REJECT = "reject"
    CANCEL_REJECT = "cancel-reject"
