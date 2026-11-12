from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.rack_elevation.mapped.mapping import RackMappingIndex
from infrahub.rack_elevation.mapped.provider import MappedRackElevationProvider

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.rack_elevation.models import (
        RackElevationKindEntry,
        RackFace,
        RackItemSnapshot,
        RackSnapshot,
    )


class RackElevationProvider(Protocol):
    """Turns a rack schema model into the normalized snapshots the shared rules work on."""

    def list_kinds(self) -> list[RackElevationKindEntry]: ...

    async def load_rack(self, rack_id: str) -> tuple[RackSnapshot, list[RackItemSnapshot]]:
        """Raise the RACK_NOT_A_RACK violation when the node is not a rack."""
        ...

    async def load_item(self, item_id: str) -> RackItemSnapshot:
        """Raise the RACK_NOT_MOUNTABLE violation when the node is not a mountable item."""
        ...

    async def place(self, item_id: str, rack_id: str, position: int | None, face: RackFace | None) -> RackItemSnapshot:
        """Move the item into the rack, checking the placement and writing in one transaction under the rack lock."""
        ...


def build_rack_elevation_provider(db: InfrahubDatabase, branch: Branch, at: Timestamp | None) -> RackElevationProvider:
    index = RackMappingIndex.from_schema_branch(schema_branch=db.schema.get_schema_branch(name=branch.name))
    return MappedRackElevationProvider(db=db, branch=branch, at=at, index=index)
