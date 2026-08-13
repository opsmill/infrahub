from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.schema.repository import InfrahubGeneratorDefinitionConfig, InfrahubPythonTransformConfig

from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.closure_builder.result import ClosureResult

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.git.closure_builder.protocols import TransformConfig


class PythonClosure:
    """Compute a Python source's dependency closure as the single file it points at.

    Handles any Python-backed config that exposes a ``file_path`` and a ``name``:
    Python transforms and generator definitions alike. Only the file named by
    ``file_path`` is auto-detected. Sitting next to that file is not evidence of being
    an input to it - a directory commonly holds several unrelated sources, each with
    its own queries and helpers - so siblings stay out of the closure and editing one
    of them does not regenerate this source's output.

    Anything the source depends on beyond its own file, such as a helper module it
    imports, is declared by the author through ``watch.files``; naming the containing
    directory there brings every tracked file beneath it back into the closure.

    ``worktree_root`` is part of the shared builder contract and unused here: naming
    the single dependency needs no filesystem access.
    """

    def supports(self, transform_config: TransformConfig) -> bool:
        return isinstance(transform_config, (InfrahubPythonTransformConfig, InfrahubGeneratorDefinitionConfig))

    def build(
        self,
        transform_config: InfrahubPythonTransformConfig | InfrahubGeneratorDefinitionConfig,
        worktree_root: Path,  # noqa: ARG002
    ) -> ClosureResult:
        entry_path = canonicalize_path(str(transform_config.file_path))
        return ClosureResult(dependencies=(entry_path,), complete=True, unresolved=())
