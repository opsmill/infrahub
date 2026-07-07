from dataclasses import dataclass

import pytest

from infrahub.events.limits import get_submission_chunk_size

ENV_VAR = "PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES"


@dataclass
class ChunkSizeCase:
    name: str
    configured_max: str
    expected: int


CHUNK_SIZE_CASES = [
    ChunkSizeCase(name="one_floored_to_one", configured_max="1", expected=1),  # 1 // 2 == 0 without the floor
    ChunkSizeCase(name="two_floored_to_one", configured_max="2", expected=1),
    ChunkSizeCase(name="ten_halved", configured_max="10", expected=5),
    ChunkSizeCase(name="default_halved", configured_max="500", expected=250),
]


@pytest.mark.parametrize("case", CHUNK_SIZE_CASES, ids=lambda case: case.name)
def test_submission_chunk_size_is_floored_at_one(case: ChunkSizeCase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, case.configured_max)
    assert get_submission_chunk_size() == case.expected
