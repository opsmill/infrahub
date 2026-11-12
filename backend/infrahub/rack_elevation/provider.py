from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

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


class UnavailableRackElevationProvider:
    """Provider for a branch without a rack model: no kind takes part and no rack can be read or written."""

    def list_kinds(self) -> list[RackElevationKindEntry]:
        return []

    async def load_rack(self, rack_id: str) -> tuple[RackSnapshot, list[RackItemSnapshot]]:
        raise NotImplementedError("No rack model on this branch")

    async def load_item(self, item_id: str) -> RackItemSnapshot:
        raise NotImplementedError("No rack model on this branch")

    async def place(
        self,
        item_id: str,
        rack_id: str,
        position: int | None,
        face: RackFace | None,
    ) -> RackItemSnapshot:
        raise NotImplementedError("No rack model on this branch")


def build_rack_elevation_provider(
    db: InfrahubDatabase,  # noqa: ARG001
    branch: Branch,  # noqa: ARG001
    at: Timestamp | None,  # noqa: ARG001
) -> RackElevationProvider:
    return UnavailableRackElevationProvider()
