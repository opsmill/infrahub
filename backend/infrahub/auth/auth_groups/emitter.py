"""Emit the auto-create audit events for one external login.

`AutoCreateEventEmitter` knows the three event shapes (`created`,
`claim_rejected`, `cap_breached`), how to build their payloads from the
login-scoped identity (account + provider_name) and the runtime dependencies
(`EmissionDeps`), and how to send each one defensively so a broker failure
cannot abort the SSO login.

When no event service is wired in, `AutoCreateEventEmitter.disabled()` returns
a Null Object so callers do not need to null-check before each emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable
from uuid import UUID

from infrahub.events.group_action import (
    GroupAutoCreateCapBreachEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedClaimEvent,
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


@dataclass(frozen=True, slots=True)
class EmissionDeps:
    """Runtime dependencies required to emit auto-create events."""

    event_service: InfrahubEventService
    event_meta_factory: Callable[[], EventMeta]
    protocol: ExternalAuthProtocol


class AutoCreateEventEmitter:
    """Emits the three auto-create audit events for one login.

    Construct directly with `(account, provider_name, deps)` when emission is
    wired up. Use `AutoCreateEventEmitter.disabled()` when no event service is
    available.
    """

    def __init__(self, *, account: CoreAccount, provider_name: str, deps: EmissionDeps) -> None:
        self._account = account
        self._provider_name = provider_name
        self._deps = deps

    @classmethod
    def disabled(cls) -> AutoCreateEventEmitter:
        return _NoopAutoCreateEventEmitter()

    async def created(self, *, group: CoreAccountGroup, source_pattern: str) -> None:
        await self._send(
            GroupAutoCreatedEvent(
                meta=self._deps.event_meta_factory(),
                idp=self._provider_name,
                triggering_user_id=UUID(self._account.id),
                triggering_user_name=self._account.name.value,
                protocol=self._deps.protocol,
                group_id=UUID(group.id),
                group_name=group.name.value,
                source_pattern=source_pattern,
                origin_value=self._provider_name,
            )
        )

    async def claim_rejected(self, *, claim: str) -> None:
        await self._send(
            GroupAutoCreateRejectedClaimEvent(
                meta=self._deps.event_meta_factory(),
                idp=self._provider_name,
                triggering_user_id=UUID(self._account.id),
                triggering_user_name=self._account.name.value,
                protocol=self._deps.protocol,
                rejected_claim_value=_truncate(claim),
            )
        )

    async def cap_breached(self, *, cap_value: int, dropped_claims: list[str]) -> None:
        await self._send(
            GroupAutoCreateCapBreachEvent(
                meta=self._deps.event_meta_factory(),
                idp=self._provider_name,
                triggering_user_id=UUID(self._account.id),
                triggering_user_name=self._account.name.value,
                protocol=self._deps.protocol,
                cap_value=cap_value,
                dropped_claims=[_truncate(claim) for claim in dropped_claims],
                dropped_count=len(dropped_claims),
            )
        )

    async def _send(self, event: InfrahubEvent) -> None:
        """Send an event, swallowing send failures so they cannot abort the login."""
        try:
            await self._deps.event_service.send(event=event)
        except Exception:
            log.exception("auth_groups.event_emission_failed", event_name=event.event_name)


class _NoopAutoCreateEventEmitter(AutoCreateEventEmitter):
    """No-op variant returned by `AutoCreateEventEmitter.disabled()`."""

    def __init__(self) -> None:
        pass

    async def created(self, *, group: CoreAccountGroup, source_pattern: str) -> None:  # noqa: ARG002
        return

    async def claim_rejected(self, *, claim: str) -> None:  # noqa: ARG002
        return

    async def cap_breached(self, *, cap_value: int, dropped_claims: list[str]) -> None:  # noqa: ARG002
        return
