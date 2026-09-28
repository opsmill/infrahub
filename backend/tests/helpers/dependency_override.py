"""Point a dependency-provider lookup at a test double and put the previous one back afterwards."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from typing import Any

    from fast_depends import Provider


@contextmanager
def override_dependency(
    original: Callable[..., Any], override: Callable[..., Any], dependency_provider: Provider
) -> Iterator[None]:
    """Resolve ``original`` through ``override`` for the duration of the block.

    The previous state comes back in a ``finally``, whether the block ends normally or through an
    exception: the override that was in place before is put back, and one that did not exist before
    is removed. (fast_depends' own ``Provider.scope`` drops its override only on a normal exit.)

    Args:
        original: The dependant whose lookups should be redirected.
        override: The callable every lookup of ``original`` should resolve through inside the block.
        dependency_provider: The provider the dependency injection resolves ``original`` through.

    """
    previous_dependant = dependency_provider.overrides.get(original)
    dependency_provider.override(original, override)
    try:
        yield
    finally:
        if previous_dependant is None:
            dependency_provider.overrides.pop(original, None)
        else:
            dependency_provider.overrides[original] = previous_dependant
