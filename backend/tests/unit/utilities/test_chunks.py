from dataclasses import dataclass, field

import pytest

from infrahub.utilities.chunks import chunked


@dataclass
class InvalidSizeCase:
    name: str
    size: int
    expected_message: str


@dataclass
class ChunkCase:
    name: str
    items: list[str] | tuple[str, ...]
    size: int
    expected: list[list[str] | tuple[str, ...]] = field(default_factory=list)


@pytest.mark.parametrize(
    "test_case",
    [
        InvalidSizeCase(name="zero", size=0, expected_message="chunk size must be greater than zero, got 0"),
        InvalidSizeCase(name="negative", size=-3, expected_message="chunk size must be greater than zero, got -3"),
    ],
    ids=lambda test_case: test_case.name,
)
def test_chunked_rejects_non_positive_chunk_size(test_case: InvalidSizeCase) -> None:
    """A non-positive chunk size is invalid and must never silently drop items."""
    with pytest.raises(ValueError, match=rf"^{test_case.expected_message}$"):
        list(chunked(["a", "b"], test_case.size))


@pytest.mark.parametrize(
    "test_case",
    [
        ChunkCase(name="empty_list", items=[], size=2, expected=[]),
        ChunkCase(name="exact_multiple", items=["a", "b", "c", "d"], size=2, expected=[["a", "b"], ["c", "d"]]),
        ChunkCase(name="trailing_partial", items=["a", "b", "c"], size=2, expected=[["a", "b"], ["c"]]),
        ChunkCase(name="size_exceeds_length", items=["a", "b"], size=5, expected=[["a", "b"]]),
        ChunkCase(name="tuple_input_stays_tuple", items=("a", "b", "c"), size=2, expected=[("a", "b"), ("c",)]),
    ],
    ids=lambda test_case: test_case.name,
)
def test_chunked_splits_into_contiguous_slices(test_case: ChunkCase) -> None:
    assert list(chunked(test_case.items, test_case.size)) == test_case.expected
