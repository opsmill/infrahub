from __future__ import annotations

from typing import Callable

import pytest
from prefect import Flow

from infrahub.message_bus.messages import MESSAGE_MAP
from infrahub.message_bus.operations import COMMAND_MAP


def test_message_command_overlap():
    """
    Verify that a command is defined for each message
    except events that don't need to be associated with a command
    """
    messages = sorted([key for key in MESSAGE_MAP.keys() if not key.startswith("event.")])
    commands = sorted([key for key in COMMAND_MAP.keys() if not key.startswith("event.")])

    assert messages == commands


@pytest.mark.parametrize(
    "operation",
    [pytest.param(function, id=key) for key, function in COMMAND_MAP.items() if not key.startswith("refresh.registry")],
)
def test_operations_decorated(operation: Callable):
    if callable(operation) and hasattr(operation, "__name__") and "Flow" not in type(operation).__name__:
        pytest.fail(f"{operation.__name__} is not decorated with @flow")
    else:
        assert isinstance(operation, Flow), f"{operation.__name__} is not a valid Prefect flow"
