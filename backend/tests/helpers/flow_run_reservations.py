from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class UnreachableReservations:
    """Reservations whose cache cannot be reached, so every call raises."""

    async def reserve(self, flow_run_id: UUID) -> bool:
        raise ConnectionError("cache unreachable")

    async def release(self, flow_run_id: UUID) -> None:
        raise ConnectionError("cache unreachable")
