import pytest

from infrahub.utilities.chunks import chunked


def test_chunked_rejects_zero_chunk_size() -> None:
    """A zero chunk size is invalid and must never reach the chunker."""
    with pytest.raises(ValueError, match="must not be zero"):
        list(chunked(["a", "b"], 0))
