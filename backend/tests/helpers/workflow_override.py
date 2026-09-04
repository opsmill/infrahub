"""Point the workflow adapter at a test double and put the previous one back afterwards."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.workers.dependencies import build_workflow

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fast_depends import Provider

    from infrahub.services.adapters.workflow import InfrahubWorkflow


@contextmanager
def override_workflow[WorkflowT: InfrahubWorkflow](
    workflow: WorkflowT, dependency_provider: Provider
) -> Iterator[WorkflowT]:
    """Route both workflow lookups to ``workflow`` for the duration of the block.

    The provider's own ``scope`` drops the override it replaced instead of restoring it, and
    neither it nor ``config.OVERRIDE`` is put back when the block is left through an exception,
    so a leftover double could reach whatever the tests build next.

    Args:
        workflow: The adapter every workflow lookup should return inside the block.
        dependency_provider: The provider the dependency injection resolves ``build_workflow`` through.

    Yields:
        ``workflow`` itself.

    """
    previous_workflow = config.OVERRIDE.workflow
    previous_dependant = dependency_provider.overrides.get(build_workflow)
    config.OVERRIDE.workflow = workflow
    dependency_provider.override(build_workflow, lambda: workflow)
    try:
        yield workflow
    finally:
        config.OVERRIDE.workflow = previous_workflow
        if previous_dependant is None:
            dependency_provider.overrides.pop(build_workflow, None)
        else:
            dependency_provider.overrides[build_workflow] = previous_dependant
