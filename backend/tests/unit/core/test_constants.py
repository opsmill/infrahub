import pytest

from infrahub.core.constants import InfrahubKind, ProposedChangeState
from infrahub.core.schema import core_models
from infrahub.exceptions import ValidationError


def test_proposed_state_transitions() -> None:
    opened = ProposedChangeState.OPEN
    closed = ProposedChangeState.CLOSED
    canceled = ProposedChangeState.CANCELED

    for allowed in ProposedChangeState.available_types():
        opened.validate_state_transition(ProposedChangeState(allowed))

    closed.validate_state_transition(opened)
    closed.validate_state_transition(canceled)

    for error_state in [ProposedChangeState.CLOSED, ProposedChangeState.MERGED]:
        with pytest.raises(ValidationError):
            closed.validate_state_transition(error_state)


def test_infrahubkind_constant_for_all_core_schema_nodes() -> None:
    "There should be an InfrahubKind constant defined for all the nodes in the core schema"

    expected_constants = sorted([node["name"].upper() for node in core_models["nodes"]])

    for constant in expected_constants:
        assert hasattr(InfrahubKind, constant)
