from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from prefect.server.events.ordering import get_triggers_causal_ordering
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.settings import PREFECT_SERVER_EVENTS_CAUSAL_ORDERING, temporary_settings
from prefect_redis.ordering import CausalOrdering as RedisCausalOrdering

from infrahub.prefect_server import ordering
from infrahub.prefect_server.ordering import CausalOrdering, needs_causal_ordering

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Collection
    from uuid import UUID


class UnreachableRedis:
    """Fails on any command, so a test proves that the ordering sent none."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the causal ordering sent the Redis command '{name}'")


def build_event(name: str, follows: UUID | None = None) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=datetime.now(tz=UTC),
        event=name,
        resource={"prefect.resource.id": f"infrahub.node.{uuid4()}"},
        id=uuid4(),
        follows=follows,
    )


def interested_triggers(triggers: Collection[object]) -> Any:
    def find(event: ReceivedEvent) -> Collection[object]:
        return triggers

    return find


async def noop_handler(event: ReceivedEvent, depth: int = 0) -> None: ...


@pytest.mark.parametrize(
    ("event_name", "follows", "triggers", "expected"),
    [
        pytest.param("infrahub.node.updated", None, [], False, id="infrahub-event-without-trigger"),
        pytest.param("infrahub.node.updated", None, [object()], True, id="infrahub-event-with-trigger"),
        pytest.param("infrahub.node.updated", uuid4(), [], True, id="infrahub-event-following-another"),
        pytest.param("prefect.flow-run.Scheduled", None, [], True, id="prefect-event-without-trigger"),
    ],
)
def test_only_infrahub_events_that_no_trigger_matches_skip_the_ordering(
    monkeypatch: pytest.MonkeyPatch, event_name: str, follows: UUID | None, triggers: list[object], expected: bool
) -> None:
    monkeypatch.setattr(ordering, "find_interested_triggers", interested_triggers(triggers))

    assert needs_causal_ordering(build_event(name=event_name, follows=follows)) is expected


async def test_an_event_that_needs_no_ordering_is_evaluated_without_redis_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ordering, "find_interested_triggers", interested_triggers([]))
    causal_ordering = CausalOrdering(scope="triggers")
    causal_ordering.redis = UnreachableRedis()  # type: ignore[assignment]
    evaluated = False

    async with causal_ordering.preceding_event_confirmed(noop_handler, build_event("infrahub.node.created")):
        evaluated = True

    assert evaluated


async def test_an_event_with_an_interested_trigger_goes_through_the_redis_ordering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ordering, "find_interested_triggers", interested_triggers([object()]))
    confirmed: list[UUID] = []

    @asynccontextmanager
    async def recording_confirmation(
        self: RedisCausalOrdering,
        handler: Any,
        event: ReceivedEvent,
        depth: int = 0,
    ) -> AsyncGenerator[None, None]:
        confirmed.append(event.id)
        yield

    monkeypatch.setattr(RedisCausalOrdering, "preceding_event_confirmed", recording_confirmation)
    event = build_event("infrahub.node.updated")

    async with CausalOrdering(scope="triggers").preceding_event_confirmed(noop_handler, event):
        pass

    assert confirmed == [event.id]


def test_prefect_loads_the_ordering_from_the_module_setting() -> None:
    with temporary_settings(updates={PREFECT_SERVER_EVENTS_CAUSAL_ORDERING: "infrahub.prefect_server.ordering"}):
        assert isinstance(get_triggers_causal_ordering(), CausalOrdering)
