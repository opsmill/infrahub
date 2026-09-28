from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

CHECKSUM_ALGORITHMS = {32: "md5", 40: "sha1"}
"""Hash algorithm of a recorded checksum, by the length of its hex digest: artifacts use MD5, files SHA-1."""


def matches_recorded_checksum(content: bytes, checksums: Collection[str]) -> bool | None:
    """Whether `content` matches one of the checksums recorded for it, or None when none can be compared."""
    comparable = {checksum.lower() for checksum in checksums if len(checksum) in CHECKSUM_ALGORITHMS}
    if not comparable:
        return None
    digests = {
        hashlib.new(CHECKSUM_ALGORITHMS[length], content, usedforsecurity=False).hexdigest()
        for length in {len(checksum) for checksum in comparable}
    }
    return not comparable.isdisjoint(digests)
