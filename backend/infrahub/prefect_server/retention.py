from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.settings.models.server.services import ServerServicesDBVacuumSettings


def deletes_old_events(vacuum: ServerServicesDBVacuumSettings) -> bool:
    """Return whether Prefect's vacuum switch turns on the deletion of old events."""
    try:
        return "events" in vacuum.enabled_vacuum_types
    except ValueError:
        # With an unknown vacuum type it is not known whether old events are deleted, so they are treated as kept.
        return False
