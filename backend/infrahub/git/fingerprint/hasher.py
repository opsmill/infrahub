"""Deterministic SHA-256 hashing and canonicalisation helpers for fingerprint composition."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


def canonical_json(value: Any) -> str:
    """Serialise a structured value to canonical JSON.

    Keys are sorted and all insignificant whitespace is removed so that logically
    identical values always produce the same string regardless of ordering.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class FingerprintHasher:
    """Compute a stable SHA-256 hex digest over an ordered sequence of canonical terms.

    Each term is length-prefixed before being folded into the digest so that no
    combination of term boundaries can be confused with another (the serialisation
    is injective across the term list).
    """

    def hash(self, terms: Sequence[str]) -> str:
        digest = hashlib.sha256()
        for term in terms:
            encoded = term.encode("utf-8")
            digest.update(f"{len(encoded)}:".encode("ascii"))
            digest.update(encoded)
        return digest.hexdigest()
