from __future__ import annotations

from typing import TYPE_CHECKING, Any

from git.exc import GitCommandError
from jinja2 import TemplateError

from infrahub.git.closure_builder.jinja2_closure import Jinja2Closure
from infrahub.git.closure_builder.jinja2_reference_resolver import Jinja2ReferenceResolver
from infrahub.git.closure_builder.post_processing import append_manifest_path
from infrahub.git.closure_builder.python_closure import PythonClosure
from infrahub.git.closure_builder.result import ClosureResult
from infrahub.git.closure_builder.watch import union_watch_files

if TYPE_CHECKING:
    import logging
    from collections.abc import Sequence
    from pathlib import Path

    from infrahub.git.closure_builder.protocols import ClosureBuilder, TransformConfig

ISOLATED_FAILURES: tuple[type[BaseException], ...] = (
    ValueError,
    OSError,
    TemplateError,
    GitCommandError,
)


class AggregatedTransformClosureBuilder:
    """Select the closure builder that supports a transform config and run it with failure isolation.

    Tries each injected builder in order and delegates to the first whose
    `supports` returns True. Failures in `ISOLATED_FAILURES` produce a fallback
    `ClosureResult` with `complete=False` so a single broken transform does not
    abort import of the rest of the repository. The canonical manifest path is
    always merged into a successful result.
    """

    def __init__(
        self,
        *,
        builders: Sequence[ClosureBuilder[Any]],
        logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
    ) -> None:
        self._builders = builders
        self._logger = logger

    def build(self, *, transform_config: TransformConfig, worktree_root: Path) -> ClosureResult:
        try:
            builder = self._select(transform_config=transform_config)
            raw = builder.build(transform_config=transform_config, worktree_root=worktree_root)
            with_manifest = append_manifest_path(result=raw)
            return union_watch_files(
                result=with_manifest,
                transform_config=transform_config,
                worktree_root=worktree_root,
                logger=self._logger,
            )
        except ISOLATED_FAILURES:
            self._logger.exception(f"Closure builder failed for transform {transform_config.name!r}")
            return ClosureResult(dependencies=(), complete=False, unresolved=())

    def _select(self, *, transform_config: TransformConfig) -> ClosureBuilder[Any]:
        for builder in self._builders:
            if builder.supports(transform_config):
                return builder
        raise NotImplementedError(
            f"No closure builder supports transform {transform_config.name!r} of type {type(transform_config).__name__}"
        )


def build_default_closure_builder(
    *,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> AggregatedTransformClosureBuilder:
    """Wire the standard per-language closure builders into an aggregator."""
    return AggregatedTransformClosureBuilder(
        builders=(
            Jinja2Closure(reference_resolver=Jinja2ReferenceResolver(), logger=logger),
            PythonClosure(),
        ),
        logger=logger,
    )
