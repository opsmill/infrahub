from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.constants.database import Neo4jRuntime

_parallel_runtime_replacement: ContextVar[Neo4jRuntime | None] = ContextVar(
    "query_cost_parallel_runtime_replacement", default=None
)


def get_parallel_runtime_replacement() -> Neo4jRuntime | None:
    """Runtime that replaces the parallel Cypher runtime in the block being run, or None outside such a block."""
    return _parallel_runtime_replacement.get()


@contextmanager
def replace_parallel_runtime(runtime: Neo4jRuntime) -> Iterator[None]:
    """Run the queries that would use the parallel runtime with `runtime` inside the block.

    This includes the tasks that the block starts. The previous runtime is restored when the block ends.
    """
    token = _parallel_runtime_replacement.set(runtime)
    try:
        yield
    finally:
        _parallel_runtime_replacement.reset(token)
