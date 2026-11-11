from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from prefect import Flow, flow
from prefect.context import FlowRunContext
from pydantic import ValidationError
from structlog.testing import capture_logs

from infrahub import config
from infrahub import trace as infrahub_trace
from infrahub.message_bus import Meta, RPCErrorResponse
from infrahub.message_bus.messages import RefreshSettingsTraceSampleRatio, SendEchoRequest
from infrahub.message_bus.operations import COMMAND_MAP, execute_message
from infrahub.message_bus.types import MessageTTL
from infrahub.trace import SampleRatioState, create_tracer_provider, get_sample_ratio_state
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.message_bus import InfrahubMessage

ECHO_ROUTING_KEY = "send.echo.request"
TRACE_SAMPLE_RATIO_ROUTING_KEY = "refresh.settings.trace_sample_ratio"
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


@pytest.fixture
def process_sampler(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Give this process a sampler with a default ratio of 0.1, and remove it after the test."""
    monkeypatch.setattr(infrahub_trace, "_process_sampler", None)
    provider = create_tracer_provider(service="infrahub-test", version="1.0", exporter_type="console", sample_ratio=0.1)
    yield
    provider.shutdown()


async def test_trace_sample_ratio_message_sets_then_clears_the_temporary_ratio(process_sampler: None) -> None:
    bus = RecordingBus()
    expires_at = datetime(2099, 1, 1, tzinfo=UTC)

    with capture_logs() as set_logs:
        set_message = RefreshSettingsTraceSampleRatio(ratio=1.0, expires_at=expires_at)
        await execute_message(
            routing_key=TRACE_SAMPLE_RATIO_ROUTING_KEY, message_body=set_message.body, message_bus=bus
        )

    assert get_sample_ratio_state() == SampleRatioState(
        default_ratio=0.1, ratio_in_force=1.0, temporary_ratio=1.0, expires_at=expires_at
    )
    assert [(log["event"], log.get("ratio"), log.get("expires_at")) for log in set_logs] == [
        ("Set the temporary trace sampling ratio", 1.0, "2099-01-01T00:00:00+00:00")
    ]

    with capture_logs() as clear_logs:
        clear_message = RefreshSettingsTraceSampleRatio(ratio=None, expires_at=None)
        await execute_message(
            routing_key=TRACE_SAMPLE_RATIO_ROUTING_KEY, message_body=clear_message.body, message_bus=bus
        )

    assert get_sample_ratio_state() == SampleRatioState(default_ratio=0.1, ratio_in_force=0.1)
    assert [log["event"] for log in clear_logs] == ["Cleared the temporary trace sampling ratio"]
    assert bus.messages == []


@dataclass
class IncompleteRatioMessageTestCase:
    name: str
    ratio: float | None
    expires_at: datetime | None


INCOMPLETE_RATIO_MESSAGE_TEST_CASES: list[IncompleteRatioMessageTestCase] = [
    IncompleteRatioMessageTestCase(name="ratio_without_expiry", ratio=1.0, expires_at=None),
    IncompleteRatioMessageTestCase(
        name="expiry_without_ratio", ratio=None, expires_at=datetime(2099, 1, 1, tzinfo=UTC)
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in INCOMPLETE_RATIO_MESSAGE_TEST_CASES])
def test_trace_sample_ratio_message_sets_ratio_and_expiry_together(test_case: IncompleteRatioMessageTestCase) -> None:
    with pytest.raises(ValidationError, match=r"ratio and expires_at must be both set or both empty"):
        RefreshSettingsTraceSampleRatio(ratio=test_case.ratio, expires_at=test_case.expires_at)
