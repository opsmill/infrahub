import pytest

from infrahub.computed_attribute.tasks import _chunk_ids


def test_chunk_ids_rejects_zero_chunk_size() -> None:
    """A zero chunk size is invalid and must never reach the chunker."""
    with pytest.raises(ValueError, match="must not be zero"):
        _chunk_ids(["a", "b"], 0)
