from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub_sdk.schema.repository import (
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
)

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.git.closure_builder.result import ClosureResult

type TransformConfig = InfrahubJinja2TransformConfig | InfrahubPythonTransformConfig


class ClosureBuilder[ConfigType](Protocol):
    """Compute a transform's dependency closure from its source files in a git worktree.

    Implementations declare which transform configs they handle via `supports`
    and compute the closure via `build`, returning a `ClosureResult` with
    canonicalized dependency paths, a completeness flag, and any unresolved
    references encountered during the walk.
    """

    def supports(self, transform_config: TransformConfig) -> bool: ...

    def build(
        self,
        transform_config: ConfigType,
        worktree_root: Path,
    ) -> ClosureResult: ...
