from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.schema.repository import InfrahubExternalTransformConfig

from infrahub.git.closure_builder.result import ClosureResult

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.git.closure_builder.protocols import TransformConfig


class ExternalClosure:
    """Return an empty, complete closure for a transform whose template lives outside the repository.

    No file in the repository affects what the external engine renders, so the closure names none
    and is complete; the declared version stands in for the template's content.
    """

    def supports(self, transform_config: TransformConfig) -> bool:
        return isinstance(transform_config, InfrahubExternalTransformConfig)

    def build(
        self,
        transform_config: InfrahubExternalTransformConfig,  # noqa: ARG002
        worktree_root: Path,  # noqa: ARG002
    ) -> ClosureResult:
        return ClosureResult(dependencies=(), complete=True, unresolved=())
