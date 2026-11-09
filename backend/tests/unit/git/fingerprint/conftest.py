from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.git.closure_builder.post_processing import MANIFEST_PATH
from infrahub.git.fingerprint.composer import ClosurePathSelector, FingerprintComposer
from infrahub.git.fingerprint.hasher import FingerprintHasher
from infrahub.git.fingerprint.registry import FingerprintRegistry

if TYPE_CHECKING:
    from collections.abc import Sequence


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
        closure_selector=ClosurePathSelector(excluded_paths=frozenset({MANIFEST_PATH})),
        commit=commit,
    )
