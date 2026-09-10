from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from prefect import Flow, flow
from prefect.context import FlowRunContext

from infrahub import config
from infrahub.message_bus import Meta, RPCErrorResponse
from infrahub.message_bus.messages import SendEchoRequest
from infrahub.message_bus.operations import COMMAND_MAP, execute_message
from infrahub.message_bus.types import MessageTTL
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from infrahub.message_bus import InfrahubMessage

ECHO_ROUTING_KEY = "send.echo.request"
OPERATIONS_MODULE = "infrahub.message_bus.operations"


class HandlerError(Exception):
    """Raised by the failing handler doubles to drive the dispatcher's error paths."""


class RecordingBus(BusRecorder):
    """Recording message bus that also keeps the replies and the delivery options of each publish."""

    def __init__(self) -> None:
        super().__init__()
        self.replies: list[tuple[InfrahubMessage, str]] = []
        self.publish_options: list[tuple[MessageTTL | None, bool]] = []

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        self.publish_options.append((delay, is_retry))
        await super().publish(message=message, routing_key=routing_key, delay=delay, is_retry=is_retry)

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        self.replies.append((message, routing_key))


class CheckStatusRecorder:
    """Check-status double that keeps the conclusion reported for each message."""

    def __init__(self) -> None:
        self.conclusions: list[tuple[InfrahubMessage, str]] = []

    async def __call__(self, message: InfrahubMessage, conclusion: str) -> None:
        self.conclusions.append((message, conclusion))


class LoggerRecorder:
    """Logger double that keeps each event reported at exception level along with its keywords."""

    def __init__(self) -> None:
        self.exceptions: list[tuple[str, dict[str, Any]]] = []

    def exception(self, event: str, **kwargs: Any) -> None:
        self.exceptions.append((event, kwargs))


@pytest.fixture
def maximum_message_retries(monkeypatch: pytest.MonkeyPatch) -> int:
    """Pin the retry ceiling the dispatcher reads, restoring whatever the environment provided."""
    ceiling = 3
    monkeypatch.setattr(config.SETTINGS.broker, "maximum_message_retries", ceiling)
    return ceiling


async def test_plain_handler_is_awaited_and_message_is_acknowledged(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful plain coroutine handler receives the decoded message and asks for no retry."""
    received: list[InfrahubMessage] = []

    async def handler(message: SendEchoRequest) -> None:
        received.append(message)

    bus = RecordingBus()
    sent = SendEchoRequest(message="ping")

    monkeypatch.setitem(COMMAND_MAP, ECHO_ROUTING_KEY, handler)
    delay = await execute_message(routing_key=ECHO_ROUTING_KEY, message_body=sent.body, message_bus=bus)

    assert len(received) == 1
    handled = received[0]
    assert isinstance(handled, SendEchoRequest)
    assert handled.message == "ping"
    assert delay is None
    assert bus.messages == []


async def test_flow_handler_is_unwrapped_when_flows_are_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """With skip_flow set, a Prefect flow handler runs as a bare coroutine rather than as a flow run."""
    received: list[InfrahubMessage] = []
    flow_run_contexts: list[FlowRunContext | None] = []

    @flow(name="unit-test-echo-handler")
    async def handler(message: SendEchoRequest) -> None:
        # A flow invoked through the Prefect engine has a run context; the unwrapped function has none.
        flow_run_contexts.append(FlowRunContext.get())
        received.append(message)

    assert isinstance(handler, Flow), "the scenario only covers the unwrap when the handler really is a flow"

    bus = RecordingBus()
    sent = SendEchoRequest(message="ping")

    monkeypatch.setitem(COMMAND_MAP, ECHO_ROUTING_KEY, handler)
    delay = await execute_message(routing_key=ECHO_ROUTING_KEY, message_body=sent.body, message_bus=bus, skip_flow=True)

    assert flow_run_contexts == [None]
    assert len(received) == 1
    handled = received[0]
    assert isinstance(handled, SendEchoRequest)
    assert handled.message == "ping"
    assert delay is None
    assert bus.messages == []


async def test_failure_with_reply_requested_returns_an_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """A handler failure on a message awaiting a reply is answered with an error and not retried."""

    async def handler(message: SendEchoRequest) -> None:
        raise HandlerError("handler exploded")

    bus = RecordingBus()
    sent = SendEchoRequest(message="ping", meta=Meta(reply_to="reply-queue", correlation_id="correlation-1"))

    monkeypatch.setitem(COMMAND_MAP, ECHO_ROUTING_KEY, handler)
    delay = await execute_message(routing_key=ECHO_ROUTING_KEY, message_body=sent.body, message_bus=bus)

    assert len(bus.replies) == 1
    response, routing_key = bus.replies[0]
    assert routing_key == "reply-queue"
    assert isinstance(response, RPCErrorResponse)
    assert response.passed is False
    assert response.errors == ["handler exploded"]
    assert response.meta.correlation_id == "correlation-1"
    assert delay is None
    assert bus.messages == []


async def test_failure_after_maximum_retries_is_logged_and_marked_failed(
    monkeypatch: pytest.MonkeyPatch, maximum_message_retries: int
) -> None:
    """A handler failure on an exhausted message is logged, marked failed and not retried again."""

    async def handler(message: SendEchoRequest) -> None:
        raise HandlerError("handler exploded")

    bus = RecordingBus()
    check_status = CheckStatusRecorder()
    logger = LoggerRecorder()
    sent = SendEchoRequest(message="ping", meta=Meta(retry_count=maximum_message_retries))

    monkeypatch.setitem(COMMAND_MAP, ECHO_ROUTING_KEY, handler)
    monkeypatch.setattr(f"{OPERATIONS_MODULE}.set_check_status", check_status)
    monkeypatch.setattr(f"{OPERATIONS_MODULE}.get_logger", lambda: logger)
    delay = await execute_message(routing_key=ECHO_ROUTING_KEY, message_body=sent.body, message_bus=bus)

    assert len(logger.exceptions) == 1
    event, keywords = logger.exceptions[0]
    assert event == "Message failed after maximum number of retries"
    assert isinstance(keywords["error"], HandlerError)
    assert str(keywords["error"]) == "handler exploded"
    assert len(check_status.conclusions) == 1
    failed_message, conclusion = check_status.conclusions[0]
    assert failed_message.meta.retry_count == maximum_message_retries
    assert conclusion == "failure"
    assert delay is None
    assert bus.messages == []


async def test_failure_with_retries_remaining_is_requeued_with_a_delay(
    monkeypatch: pytest.MonkeyPatch, maximum_message_retries: int
) -> None:
    """A handler failure with retries left re-sends the message with a delay and returns that delay."""

    async def handler(message: SendEchoRequest) -> None:
        raise HandlerError("handler exploded")

    bus = RecordingBus()
    sent = SendEchoRequest(message="ping", meta=Meta(retry_count=maximum_message_retries - 2))

    monkeypatch.setitem(COMMAND_MAP, ECHO_ROUTING_KEY, handler)
    delay = await execute_message(routing_key=ECHO_ROUTING_KEY, message_body=sent.body, message_bus=bus)

    assert len(bus.messages) == 1
    assert bus.messages[0].meta.retry_count == maximum_message_retries - 1
    assert bus.seen_routing_keys == [ECHO_ROUTING_KEY]
    assert bus.publish_options == [(MessageTTL.FIVE, True)]
    assert delay == MessageTTL.FIVE
