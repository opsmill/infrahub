import pytest

from infrahub.core.constants import ProposedChangeState
from infrahub.exceptions import ValidationError


def test_proposed_state_transitions() -> None:
    opened = ProposedChangeState.OPEN
    closed = ProposedChangeState.CLOSED
    canceled = ProposedChangeState.CANCELED
    merged = ProposedChangeState.MERGED

    for allowed in ProposedChangeState.available_types():
        opened.validate_state_transition(ProposedChangeState(allowed))

    closed.validate_state_transition(opened)
    closed.validate_state_transition(canceled)

    for error_state in [ProposedChangeState.CLOSED, ProposedChangeState.MERGED]:
        with pytest.raises(ValidationError):
            closed.validate_state_transition(error_state)

    for disallowed in ProposedChangeState.available_types():
        with pytest.raises(ValidationError):
            canceled.validate_state_transition(ProposedChangeState(disallowed))

    for disallowed in ProposedChangeState.available_types():
        with pytest.raises(ValidationError):
            merged.validate_state_transition(ProposedChangeState(disallowed))
