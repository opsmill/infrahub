import os
from collections.abc import Iterator

import pytest

from infrahub.computed_attribute.tasks import (
    _chunk_ids,
    _get_submission_chunk_size,
)

ENV_VAR = "PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES"


@pytest.fixture
def configured_max(request: pytest.FixtureRequest) -> Iterator[str]:
    value: str = request.param
    original = os.environ.get(ENV_VAR)
    os.environ[ENV_VAR] = value
    yield value
    if original is None:
        os.environ.pop(ENV_VAR, None)
    else:
        os.environ[ENV_VAR] = original


def test_chunk_ids_rejects_zero_chunk_size() -> None:
    """A zero chunk size is invalid and must never reach the chunker."""
    with pytest.raises(ValueError, match="must not be zero"):
        _chunk_ids(["a", "b"], 0)


@pytest.mark.parametrize(
    ("configured_max", "expected"),
    [
        ("1", 1),  # 1 // 2 == 0 without the floor, which would break batching
        ("2", 1),
        ("10", 5),
        ("500", 250),
    ],
    indirect=["configured_max"],
)
def test_submission_chunk_size_is_floored_at_one(configured_max: str, expected: int) -> None:
    chunk_size = _get_submission_chunk_size()
    assert chunk_size == expected
    # The computed size is always usable by the chunker, never zero.
    assert _chunk_ids(["a", "b", "c"], chunk_size)
