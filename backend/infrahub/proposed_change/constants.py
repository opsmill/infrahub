from __future__ import annotations

from infrahub.exceptions import ValidationError
from infrahub.utils import InfrahubStringEnum


class ProposedChangeState(InfrahubStringEnum):
    OPEN = "open"
    MERGED = "merged"
    MERGING = "merging"
    CLOSED = "closed"
    CANCELED = "canceled"

    def validate_state_check_run(self) -> None:
        if self == ProposedChangeState.OPEN:
            return

        raise ValidationError(input_value="Unable to trigger check on proposed changes that aren't in the open state")

    def validate_editability(self) -> None:
        if self in [ProposedChangeState.CANCELED, ProposedChangeState.MERGED, ProposedChangeState.MERGED]:
            raise ValidationError(
                input_value=f"A proposed change in the {self.value} state is not allowed to be updated"
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
