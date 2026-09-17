import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import pytest

from infrahub.exceptions import WorkerTimeoutError
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.messages.git_repository_connectivity import GitRepositoryConnectivityResponse
from infrahub.message_bus.types import MessageTTL
from tests.adapters.message_bus import CALLBACK_QUEUE_NAME, NeverReplyingBus, NeverReplyingNATSBus

if TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage
    from nats.aio.msg import Msg

TIMEOUT_SECONDS = 1
ROUTING_KEY = "git.repository.connectivity"

NeverReplying = NeverReplyingBus | NeverReplyingNATSBus


@dataclass
class IncomingAMQPMessage:
    correlation_id: str | None
    routing_key: str = ROUTING_KEY


@dataclass
class IncomingNATSMessage:
    headers: dict[str, str] = field(default_factory=dict)
    subject: str = ROUTING_KEY


def amqp_reply(correlation_id: str | None) -> "AbstractIncomingMessage":
    """A reply carrying only the fields the callback reads."""
    return cast("AbstractIncomingMessage", IncomingAMQPMessage(correlation_id=correlation_id))


def nats_reply(correlation_id: str) -> "Msg":
    """A reply carrying only the fields the callback reads."""
    return cast("Msg", IncomingNATSMessage(headers={"correlation_id": correlation_id}))


@pytest.fixture
def connectivity_message() -> messages.GitRepositoryConnectivity:
    return messages.GitRepositoryConnectivity(
        repository_name="repo-01",
        repository_location="https://mock/repo-01.git",
    )


@pytest.fixture(params=["rabbitmq", "nats"])
async def never_replying_bus(request: pytest.FixtureRequest) -> NeverReplying:
    if request.param == "rabbitmq":
        return NeverReplyingBus(rpc_timeout=TIMEOUT_SECONDS)
    return NeverReplyingNATSBus(rpc_timeout=TIMEOUT_SECONDS)


async def test_rpc_gives_up_on_a_worker_that_never_answers(
    never_replying_bus: NeverReplying, connectivity_message: messages.GitRepositoryConnectivity
) -> None:
    started = time.monotonic()
    with pytest.raises(
        WorkerTimeoutError, match=r"^No worker answered git\.repository\.connectivity within 1 seconds$"
    ):
        await never_replying_bus.rpc(message=connectivity_message, response_class=GitRepositoryConnectivityResponse)
    elapsed = time.monotonic() - started

    assert TIMEOUT_SECONDS <= elapsed < TIMEOUT_SECONDS * 2
    assert never_replying_bus.futures == {}


async def test_rpc_addresses_the_reply_to_its_own_callback_queue(
    never_replying_bus: NeverReplying, connectivity_message: messages.GitRepositoryConnectivity
) -> None:
    with pytest.raises(WorkerTimeoutError, match=r"^No worker answered "):
        await never_replying_bus.rpc(message=connectivity_message, response_class=GitRepositoryConnectivityResponse)

    assert len(never_replying_bus.messages) == 1
    sent = never_replying_bus.messages[0]
    assert sent.meta.reply_to == CALLBACK_QUEUE_NAME
    assert sent.meta.correlation_id


async def test_rpc_honours_an_explicit_timeout_over_the_configured_one(
    connectivity_message: messages.GitRepositoryConnectivity,
) -> None:
    bus = NeverReplyingBus(rpc_timeout=3600)

    started = time.monotonic()
    with pytest.raises(
        WorkerTimeoutError, match=r"^No worker answered git\.repository\.connectivity within 1 seconds$"
    ):
        await bus.rpc(message=connectivity_message, response_class=GitRepositoryConnectivityResponse, timeout=1)

    assert time.monotonic() - started < 10


async def test_a_failed_publish_leaves_no_pending_request_behind(
    connectivity_message: messages.GitRepositoryConnectivity,
) -> None:
    class UnpublishableBus(NeverReplyingBus):
        async def publish(
            self,
            message: InfrahubMessage,
            routing_key: str,
            delay: MessageTTL | None = None,
            is_retry: bool = False,
        ) -> None:
            raise ConnectionResetError("broker went away")

    bus = UnpublishableBus()

    with pytest.raises(ConnectionResetError, match=r"^broker went away$"):
        await bus.rpc(message=connectivity_message, response_class=GitRepositoryConnectivityResponse)

    assert bus.futures == {}


async def test_amqp_reply_for_an_abandoned_request_is_dropped_quietly() -> None:
    bus = NeverReplyingBus()

    await bus.on_callback(amqp_reply(correlation_id="never-registered"))

    assert bus.futures == {}


async def test_nats_reply_for_an_abandoned_request_is_dropped_quietly() -> None:
    bus = NeverReplyingNATSBus()

    await bus.on_callback(nats_reply(correlation_id="never-registered"))

    assert bus.futures == {}


async def test_amqp_reply_arriving_after_the_timeout_cancelled_the_future_is_dropped_quietly() -> None:
    bus = NeverReplyingBus()
    correlation_id = "cancelled-by-timeout"
    future = bus.loop.create_future()
    future.cancel()
    bus.futures[correlation_id] = future

    await bus.on_callback(amqp_reply(correlation_id=correlation_id))

    assert bus.futures == {}


async def test_amqp_reply_still_resolves_a_waiting_request() -> None:
    bus = NeverReplyingBus()
    correlation_id = "waiting"
    future = bus.loop.create_future()
    bus.futures[correlation_id] = future
    reply = amqp_reply(correlation_id=correlation_id)

    await bus.on_callback(reply)

    assert await asyncio.wait_for(future, timeout=1) is reply
    assert bus.futures == {}
