from __future__ import annotations

from typing import Callable

import pytest
from prefect import Flow

from infrahub.message_bus.messages import MESSAGE_MAP
from infrahub.message_bus.operations import COMMAND_MAP


def test_message_command_overlap():
    """Verify that a command is defined for each message."""
    messages = sorted(list(MESSAGE_MAP.keys()))
    commands = sorted(list(COMMAND_MAP.keys()))
    assert messages == commands


@pytest.mark.parametrize(
    "operation",
    [pytest.param(function, id=key) for key, function in COMMAND_MAP.items()],
)
def test_operations_decorated(operation: Callable):
    if callable(operation) and hasattr(operation, "__name__") and "Flow" not in type(operation).__name__:
        pytest.fail(f"{operation.__name__} is not decorated with @flow")
    else:
        assert isinstance(operation, Flow), f"{operation.__name__} is not a valid Prefect flow"
