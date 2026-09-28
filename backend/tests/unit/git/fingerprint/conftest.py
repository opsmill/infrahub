from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.git.fingerprint.composer import FingerprintComposer
from infrahub.git.fingerprint.hasher import FingerprintHasher
from infrahub.git.fingerprint.registry import FingerprintRegistry

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class NonCanonicalPathCase:
    name: str
    value: str


NON_CANONICAL_PATH_CASES = [
    NonCanonicalPathCase(name="leading_slash", value="/transforms/report.py"),
    NonCanonicalPathCase(name="leading_dot_slash", value="./transforms/report.py"),
    NonCanonicalPathCase(name="backslash_separator", value="transforms\\report.py"),
    NonCanonicalPathCase(name="trailing_slash", value="transforms/report.py/"),
]


def expected_rejection(*, field: str, value: str) -> str:
    """The anchored pattern matching the rejection raised for a non-canonical path."""
    message = f"{field} {value!r} is not in canonical form; it must satisfy canonicalize_path(p) == p"
    return f"^{re.escape(message)}$"


class StaticBlobResolver:
    """In-memory blob resolver returning fixed SHAs for a known path->sha mapping.

    An unknown path resolves to an empty SHA, mirroring the git resolver's behaviour
    for a path missing from the tree.
    """

    def __init__(self, blob_shas: dict[str, str]) -> None:
        self._blob_shas = blob_shas

    def resolve(self, paths: Sequence[str]) -> list[tuple[str, str]]:
        return sorted((path, self._blob_shas.get(path, "")) for path in paths)


def build_composer(
    *,
    blob_shas: dict[str, str] | None = None,
    commit: str = "commit-aaaa",
    registry: FingerprintRegistry | None = None,
) -> FingerprintComposer:
    return FingerprintComposer(
        hasher=FingerprintHasher(),
        blob_resolver=StaticBlobResolver(blob_shas or {}),
        registry=registry or FingerprintRegistry(),
        commit=commit,
    )
