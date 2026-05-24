"""Emit the auto-create audit events for one external login.

Defines the `AutoCreateEventEmitter` interface and two peer implementations:
`LiveAutoCreateEventEmitter` sends the three event shapes (`created`,
`claim_rejected`, `cap_breached`) defensively so a broker failure cannot
abort the SSO login; `DisabledAutoCreateEventEmitter` is the Null Object
used when no event service is wired in, so callers do not need to null-check
before each emit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable
from uuid import UUID

from infrahub.events.group_action import (
    GroupAutoCreateCappedEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedEvent,
)
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreAccount, CoreAccountGroup
    from infrahub.events.models import EventMeta, InfrahubEvent
    from infrahub.external_protocols import ExternalAuthProtocol
    from infrahub.services.adapters.event import InfrahubEventService

log = get_logger()

MAX_CLAIM_VALUE_LENGTH = 1024


def _truncate(value: str) -> str:
    if len(value) <= MAX_CLAIM_VALUE_LENGTH:
        return value
    return value[:MAX_CLAIM_VALUE_LENGTH]


class AutoCreateEventEmitter(ABC):
    """Interface for emitting the three auto-create audit events for one login."""

    @abstractmethod
    async def created(self, *, group: CoreAccountGroup, source_pattern: str) -> None: ...

    @abstractmethod
    async def claim_rejected(self, *, claim: str) -> None: ...

    @abstractmethod
    async def cap_breached(self, *, cap_value: int, dropped_claims: list[str]) -> None: ...


class LiveAutoCreateEventEmitter(AutoCreateEventEmitter):
    """Sends the three auto-create audit events through an `InfrahubEventService`."""

    def __init__(
        self,
        *,
        account: CoreAccount,
        provider_name: str,
        event_service: InfrahubEventService,
        event_meta_factory: Callable[[], EventMeta],
        protocol: ExternalAuthProtocol,
    ) -> None:
        self._account = account
        self._provider_name = provider_name
        self._event_service = event_service
        self._event_meta_factory = event_meta_factory
        self._protocol = protocol

    async def created(self, *, group: CoreAccountGroup, source_pattern: str) -> None:
        await self._send(
            GroupAutoCreatedEvent(
                meta=self._event_meta_factory(),
                idp=self._provider_name,
                triggering_user_id=UUID(self._account.id),
                triggering_user_name=self._account.name.value,
                protocol=self._protocol,
                group_id=UUID(group.id),
                group_name=group.name.value,
                source_pattern=source_pattern,
                origin_value=self._provider_name,
            )
        )

    async def claim_rejected(self, *, claim: str) -> None:
        await self._send(
            GroupAutoCreateRejectedEvent(
                meta=self._event_meta_factory(),
                idp=self._provider_name,
                triggering_user_id=UUID(self._account.id),
                triggering_user_name=self._account.name.value,
                protocol=self._protocol,
                rejected_claim_value=_truncate(claim),
            )
        )

    async def cap_breached(self, *, cap_value: int, dropped_claims: list[str]) -> None:
        await self._send(
            GroupAutoCreateCappedEvent(
                meta=self._event_meta_factory(),
                idp=self._provider_name,
                triggering_user_id=UUID(self._account.id),
                triggering_user_name=self._account.name.value,
                protocol=self._protocol,
                cap_value=cap_value,
                dropped_claims=[_truncate(claim) for claim in dropped_claims],
                dropped_count=len(dropped_claims),
            )
        )

    async def _send(self, event: InfrahubEvent) -> None:
        """Send an event, swallowing send failures so they cannot abort the login."""
        try:
            await self._event_service.send(event=event)
        except Exception:
            log.exception("auth_groups.event_emission_failed", event_name=event.event_name)


class DisabledAutoCreateEventEmitter(AutoCreateEventEmitter):
    """Null Object emitter used when no event service is wired in."""

    async def created(self, *, group: CoreAccountGroup, source_pattern: str) -> None:  # noqa: ARG002
        return

    async def claim_rejected(self, *, claim: str) -> None:  # noqa: ARG002
        return

    async def cap_breached(self, *, cap_value: int, dropped_claims: list[str]) -> None:  # noqa: ARG002
        return
