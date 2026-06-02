from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from git.exc import GitCommandError
from infrahub_sdk.schema.repository import (
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
)
from jinja2 import TemplateError

from infrahub.git.closure_builder.jinja2_closure import Jinja2Closure
from infrahub.git.closure_builder.post_processing import append_manifest_path
from infrahub.git.closure_builder.python_closure import PythonClosure
from infrahub.git.closure_builder.result import ClosureResult

if TYPE_CHECKING:
    import logging
    from pathlib import Path

    from infrahub.git.closure_builder.protocols import TransformConfig

ISOLATED_FAILURES: tuple[type[BaseException], ...] = (
    ValueError,
    OSError,
    TemplateError,
    GitCommandError,
)


def build_transform_closure(
    *,
    transform_config: TransformConfig,
    worktree_root: Path,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
) -> ClosureResult:
    """Compute a transform's stored dependency closure with the manifest path included.

    Returns a `ClosureResult` whose `dependencies` always include the canonical
    manifest path. Failures listed in `ISOLATED_FAILURES` produce a fallback
    result with `complete=False` and `dependencies=()`; anything outside that
    set propagates.
    """
    try:
        match transform_config:
            case InfrahubJinja2TransformConfig():
                raw = Jinja2Closure().build(transform_config=transform_config, worktree_root=worktree_root)
            case InfrahubPythonTransformConfig():
                raw = PythonClosure().build(transform_config=transform_config, worktree_root=worktree_root)
            case _:
                assert_never(transform_config)
    except ISOLATED_FAILURES:
        if logger is not None:
            logger.exception(f"Closure builder failed for transform {transform_config.name!r}")
        return ClosureResult(dependencies=(), complete=False, unresolved=())

    return append_manifest_path(result=raw)
