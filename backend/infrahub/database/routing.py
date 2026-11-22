from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from neo4j import READ_ACCESS, WRITE_ACCESS

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from neo4j import AsyncDriver

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


@dataclass(frozen=True)
class SessionRoute:
    driver: AsyncDriver
    access_mode: str
    """`READ_ACCESS` runs the session on a reader allowed by the policy of the driver, `WRITE_ACCESS` on the writer."""


class PriorityReadRouting:
    """Routes of the read sessions of the priorities that have a routing policy or read from the writer.

    The routing policy of a Neo4j driver is fixed when the driver is created, so each policy has a driver of its own.
    """

    def __init__(self, routes: Mapping[WorkflowPriority, SessionRoute], owned_drivers: Sequence[AsyncDriver]) -> None:
        self._routes = dict(routes)
        self._owned_drivers = list(owned_drivers)

    def route(self, priority: WorkflowPriority | None) -> SessionRoute | None:
        """Route of a read session that serves `priority`, or None when that priority has no route of its own."""
        if priority is None:
            return None
        return self._routes.get(priority)

    async def verify_connectivity(self) -> None:
        """Open a read connection through every owned driver, which fails when the cluster lacks its policy.

        Raises:
            neo4j.exceptions.Neo4jError: When the cluster rejects the routing policy of a driver.
            neo4j.exceptions.DriverError: When a driver cannot reach a server of the cluster.

        """
        for driver in self._owned_drivers:
            await driver.verify_connectivity()

    async def close(self) -> None:
        for driver in self._owned_drivers:
            await driver.close()


def select_session_route(
    *,
    default_driver: AsyncDriver,
    read_only: bool,
    read_routing: PriorityReadRouting | None,
    priority: WorkflowPriority | None,
) -> SessionRoute:
    """Driver and access mode of a new session.

    A routing policy filters only the readers of a cluster, and the writer runs every write, so a write session always
    uses the default driver.
    """
    if not read_only:
        return SessionRoute(driver=default_driver, access_mode=WRITE_ACCESS)
    route = read_routing.route(priority=priority) if read_routing is not None else None
    if route is not None:
        return route
    return SessionRoute(driver=default_driver, access_mode=READ_ACCESS)
