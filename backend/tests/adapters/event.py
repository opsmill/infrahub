from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.auth.auth_groups.emitter import AutoCreateEventEmitter
from infrahub.services.adapters.event import InfrahubEventService

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreAccountGroup
    from infrahub.events import InfrahubEvent


class MemoryInfrahubEvent(InfrahubEventService):
    def __init__(self) -> None:
        self.events: list[InfrahubEvent] = []

    async def send(self, event: InfrahubEvent) -> None:
        self.events.append(event)


class FailingKindInfrahubEvent(MemoryInfrahubEvent):
    """Records every event but raises on the ones of a given type."""

    def __init__(self, failing_kind: type[InfrahubEvent]) -> None:
        super().__init__()
        self.failing_kind = failing_kind

    async def send(self, event: InfrahubEvent) -> None:
        if isinstance(event, self.failing_kind):
            raise RuntimeError(f"{type(event).__name__} rejected")
        await super().send(event=event)


class RecordingAutoCreateEventEmitter(AutoCreateEventEmitter):
    """Records the auto-group audit events emitted during one assignment."""

    def __init__(self) -> None:
        self.created_groups: list[str] = []
        self.rejected_claims: list[str] = []
        self.cap_values: list[int] = []

    async def created(self, *, group: CoreAccountGroup, source_pattern: str) -> None:
        self.created_groups.append(group.name.value)

    async def claim_rejected(self, *, claim: str) -> None:
        self.rejected_claims.append(claim)

    async def cap_breached(self, *, cap_value: int, dropped_claims: list[str]) -> None:
        self.cap_values.append(cap_value)
