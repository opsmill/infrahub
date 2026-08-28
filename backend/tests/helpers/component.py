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

    Without it a flow waiting for the schema finds no worker and burns the whole timeout.
    """
    component = InfrahubComponent(cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.GIT_AGENT)
    await component.refresh_heartbeat()
    return component
