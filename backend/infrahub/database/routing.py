from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from neo4j import READ_ACCESS, WRITE_ACCESS

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.workflows.constants import WorkflowPriority

_execution_priority: ContextVar[WorkflowPriority | None] = ContextVar("infrahub_execution_priority", default=None)


def get_execution_priority() -> WorkflowPriority | None:
    """Priority of the API request or workflow run that the current task serves, or None outside of one."""
    return _execution_priority.get()


@contextmanager
def bind_execution_priority(priority: WorkflowPriority | None) -> Iterator[None]:
    """Make `priority` the execution priority of the current task and of the tasks it starts, until exit."""
    token = _execution_priority.set(priority)
    try:
        yield
    finally:
        _execution_priority.reset(token)


def session_access_mode(
    *, read_only: bool, priority: WorkflowPriority | None, writer_read_priorities: frozenset[WorkflowPriority]
) -> str:
    """Access mode of a new session, which a cluster uses to run it on the writer or on a reader.

    A read session that serves one of `writer_read_priorities` opens in write mode so that it runs on the writer.
    """
    if not read_only or priority in writer_read_priorities:
        return WRITE_ACCESS
    return READ_ACCESS
