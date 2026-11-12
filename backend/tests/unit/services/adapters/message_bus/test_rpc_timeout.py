import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from infrahub.exceptions import WorkerTimeoutError
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import GitRepositoryConnectivityResponse
from tests.adapters.message_bus import (
    CALLBACK_QUEUE_NAME,
    NeverReplyingBus,
    StalledPublishBus,
    TimingOutPublishBus,
    UnreachableBrokerBus,
)

if TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage

TIMEOUT_SECONDS = 1
CONFIGURED_TIMEOUT_SECONDS = 5
# Only an explicit `timeout=` reaches below a second; the setting is whole seconds with a floor of one.
BRIEF_TIMEOUT_SECONDS = 0.05
ROUTING_KEY = "git.repository.connectivity"


@dataclass
class IncomingAMQPMessage:
    correlation_id: str | None
    routing_key: str = ROUTING_KEY


def amqp_reply(correlation_id: str | None) -> "AbstractIncomingMessage":
    """A reply carrying only the fields the callback reads."""
    return cast("AbstractIncomingMessage", IncomingAMQPMessage(correlation_id=correlation_id))


@pytest.fixture
def connectivity_message() -> messages.GitRepositoryConnectivity:
    return messages.GitRepositoryConnectivity(
        repository_name="repo-01",
        repository_location="https://mock/repo-01.git",
    )


@pytest.fixture
async def never_replying_bus() -> NeverReplyingBus:
    return NeverReplyingBus(rpc_timeout=TIMEOUT_SECONDS)


@pytest.fixture
async def unreachable_broker_bus() -> UnreachableBrokerBus:
    return UnreachableBrokerBus()


@pytest.fixture
async def stalled_publish_bus() -> StalledPublishBus:
    return StalledPublishBus(rpc_timeout=CONFIGURED_TIMEOUT_SECONDS)


@pytest.fixture
async def timing_out_publish_bus() -> TimingOutPublishBus:
    return TimingOutPublishBus(rpc_timeout=CONFIGURED_TIMEOUT_SECONDS)


async def test_rpc_gives_up_on_a_worker_that_never_answers(
    never_replying_bus: NeverReplyingBus, connectivity_message: messages.GitRepositoryConnectivity
) -> None:
    started = time.monotonic()
    with pytest.raises(
        WorkerTimeoutError, match=r"^No worker answered git\.repository\.connectivity within 1 seconds$"
    ):
        await never_replying_bus.rpc(message=connectivity_message, response_class=GitRepositoryConnectivityResponse)
    elapsed = time.monotonic() - started

    assert TIMEOUT_SECONDS <= elapsed < 10
    assert never_replying_bus.futures == {}


async def test_rpc_addresses_the_reply_to_its_own_callback_queue(
    never_replying_bus: NeverReplyingBus, connectivity_message: messages.GitRepositoryConnectivity
) -> None:
    with pytest.raises(
        WorkerTimeoutError, match=r"^No worker answered git\.repository\.connectivity within 0\.05 seconds$"
    ):
        await never_replying_bus.rpc(
            message=connectivity_message,
            response_class=GitRepositoryConnectivityResponse,
            timeout=BRIEF_TIMEOUT_SECONDS,
        )

    assert len(never_replying_bus.messages) == 1
    sent = never_replying_bus.messages[0]
    assert sent.meta.reply_to == CALLBACK_QUEUE_NAME
    assert sent.meta.correlation_id


async def test_rpc_honours_an_explicit_timeout_over_the_configured_one(
    connectivity_message: messages.GitRepositoryConnectivity,
) -> None:
    # Kept close to the explicit bound so a regression fails the suite rather than hanging it.
    bus = NeverReplyingBus(rpc_timeout=CONFIGURED_TIMEOUT_SECONDS)

    started = time.monotonic()
    with pytest.raises(
        WorkerTimeoutError, match=r"^No worker answered git\.repository\.connectivity within 0.05 seconds$"
    ):
        await bus.rpc(
            message=connectivity_message,
            response_class=GitRepositoryConnectivityResponse,
            timeout=BRIEF_TIMEOUT_SECONDS,
        )

    assert time.monotonic() - started < 10


async def test_a_failed_publish_leaves_no_pending_request_behind(
    unreachable_broker_bus: UnreachableBrokerBus, connectivity_message: messages.GitRepositoryConnectivity
) -> None:
    with pytest.raises(ConnectionResetError, match=r"^broker went away$"):
        await unreachable_broker_bus.rpc(message=connectivity_message, response_class=GitRepositoryConnectivityResponse)

    assert unreachable_broker_bus.futures == {}


async def test_a_publish_that_never_completes_is_bounded_too(
    stalled_publish_bus: StalledPublishBus, connectivity_message: messages.GitRepositoryConnectivity
) -> None:
    started = time.monotonic()
    with pytest.raises(
        WorkerTimeoutError, match=r"^No worker answered git\.repository\.connectivity within 0\.05 seconds$"
    ):
        await stalled_publish_bus.rpc(
            message=connectivity_message,
            response_class=GitRepositoryConnectivityResponse,
            timeout=BRIEF_TIMEOUT_SECONDS,
        )

    assert time.monotonic() - started < 10
    assert stalled_publish_bus.futures == {}


async def test_a_broker_timeout_is_not_reported_as_an_unanswered_request(
    timing_out_publish_bus: TimingOutPublishBus, connectivity_message: messages.GitRepositoryConnectivity
) -> None:
    with pytest.raises(TimeoutError, match=r"^broker publish timed out$"):
        await timing_out_publish_bus.rpc(message=connectivity_message, response_class=GitRepositoryConnectivityResponse)

    assert timing_out_publish_bus.futures == {}


async def test_reply_for_an_abandoned_request_is_dropped_quietly(never_replying_bus: NeverReplyingBus) -> None:
    await never_replying_bus.on_callback(amqp_reply(correlation_id="never-registered"))

    assert never_replying_bus.futures == {}


async def test_reply_arriving_after_the_timeout_cancelled_the_future_is_dropped_quietly(
    never_replying_bus: NeverReplyingBus,
) -> None:
    correlation_id = "cancelled-by-timeout"
    future = never_replying_bus.loop.create_future()
    future.cancel()
    never_replying_bus.futures[correlation_id] = future

    await never_replying_bus.on_callback(amqp_reply(correlation_id=correlation_id))

    assert never_replying_bus.futures == {}


async def test_reply_still_resolves_a_waiting_request(never_replying_bus: NeverReplyingBus) -> None:
    correlation_id = "waiting"
    future = never_replying_bus.loop.create_future()
    never_replying_bus.futures[correlation_id] = future
    reply = amqp_reply(correlation_id=correlation_id)

    await never_replying_bus.on_callback(reply)

    assert await asyncio.wait_for(future, timeout=TIMEOUT_SECONDS) is reply
    assert never_replying_bus.futures == {}
