import hashlib
from typing import Any

import pytest

from infrahub.core.graph.schema import get_attribute_value_key


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param('{"id":"one"}', _md5('{"id":"one"}'), id="string-is-hashed-as-is"),
        pytest.param({"id": "one"}, _md5('{"id":"one"}'), id="non-string-is-hashed-serialized"),
        pytest.param(5, _md5("5"), id="number-is-hashed-serialized"),
    ],
)
def test_get_attribute_value_key(value: Any, expected: str) -> None:
    assert get_attribute_value_key(value) == expected


def test_get_attribute_value_key_has_a_fixed_size_for_a_value_too_large_to_index() -> None:
    key = get_attribute_value_key("x" * 10_000)

    assert len(key) == 32
    assert key != get_attribute_value_key("x" * 10_001)
