from __future__ import annotations

from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.closure_builder.result import ClosureResult

MANIFEST_PATH = ".infrahub.yml"


def append_manifest_path(*, result: ClosureResult) -> ClosureResult:
    """Return a new `ClosureResult` with `.infrahub.yml` merged into dependencies."""
    canonical_manifest = canonicalize_path(MANIFEST_PATH)
    merged = sorted(set(result.dependencies) | {canonical_manifest})
    return ClosureResult(
        dependencies=tuple(merged),
        complete=result.complete,
        unresolved=result.unresolved,
    )
