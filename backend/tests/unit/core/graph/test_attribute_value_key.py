from typing import Any

import pytest

from infrahub.constants.database import ATTRIBUTE_VALUE_KEY_LENGTH
from infrahub.core.graph.schema import get_attribute_value_key


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param('{"id":"one"}', '{"id":"one"}', id="short-string-is-its-own-key"),
        pytest.param(
            "x" * (ATTRIBUTE_VALUE_KEY_LENGTH + 1), "x" * ATTRIBUTE_VALUE_KEY_LENGTH, id="long-string-is-truncated"
        ),
        pytest.param({"id": "one"}, '{"id":"one"}', id="non-string-is-serialized"),
        pytest.param(5, "5", id="number-is-serialized"),
    ],
)
def test_get_attribute_value_key(value: Any, expected: str) -> None:
    assert get_attribute_value_key(value) == expected
