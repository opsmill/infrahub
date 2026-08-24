"""A worker component for tests that call worker flows directly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.components import ComponentType
from infrahub.services.component import InfrahubComponent
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.cache import InfrahubCache


async def build_worker_component(*, db: InfrahubDatabase, cache: InfrahubCache) -> InfrahubComponent:
    """A task-worker component whose heartbeat is already recorded in ``cache``.

    A flow that waits for the schema to converge reads the worker registry out of the cache. With no
    heartbeat there it finds no worker at all, and waits for the whole timeout before giving up.
    """
    component = InfrahubComponent(cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.GIT_AGENT)
    await component.refresh_heartbeat()
    return component
