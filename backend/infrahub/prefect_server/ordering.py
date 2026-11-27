"""Causal ordering for the Prefect triggers consumer, selected with `PREFECT_SERVER_EVENTS_CAUSAL_ORDERING`.

Infrahub sends far more events than Prefect itself, and almost none of them match an automation. The
ordering that prefect-redis 0.3 provides spends three Redis round trips on every event (the seen check,
the processing mark and the completion script) before Prefect 3.8 looks for an interested trigger.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from prefect.server.events.triggers import find_interested_triggers
from prefect_redis.ordering import CausalOrdering as RedisCausalOrdering

from infrahub.events.constants import EVENT_NAMESPACE

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from prefect.server.events.ordering import event_handler
    from prefect.server.events.schemas.events import ReceivedEvent

INFRAHUB_EVENT_PREFIX = f"{EVENT_NAMESPACE}."


def needs_causal_ordering(event: ReceivedEvent) -> bool:
    """Return whether the triggers consumer must record the event in the causal ordering.

    The ordering serves two purposes: an event that follows another one waits for it, and an event
    delivered twice is evaluated once. An Infrahub event follows no event, no event follows it, and
    evaluating it twice is harmless when no trigger is interested in it, so such an event needs neither.
    """
    if event.follows is not None or not event.event.startswith(INFRAHUB_EVENT_PREFIX):
        return True
    return bool(find_interested_triggers(event))


class CausalOrdering(RedisCausalOrdering):
    """The prefect-redis causal ordering, skipped for the Infrahub events that no automation matches."""

    @asynccontextmanager
    async def preceding_event_confirmed(
        self,
        handler: event_handler,
        event: ReceivedEvent,
        depth: int = 0,
    ) -> AsyncGenerator[None, None]:
        if not needs_causal_ordering(event):
            yield
            return

        async with super().preceding_event_confirmed(handler=handler, event=event, depth=depth):
            yield
