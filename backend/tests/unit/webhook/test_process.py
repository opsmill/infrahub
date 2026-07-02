from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
import pytest
import ujson

from infrahub.exceptions import HTTPServerError
from infrahub.webhook.classifier import WebhookDeliveryError
from infrahub.webhook.models import CustomWebhook, HeaderKind, Webhook, WebhookHeader
from infrahub.webhook.tasks import process
from infrahub.webhook.tasks.process import (
    PAYLOAD_LOG_LIMIT,
    WEBHOOK_SEND_ATTEMPTS,
    webhook_post,
    webhook_send,
)

if TYPE_CHECKING:
    from collections.abc import Callable

LOGGER_NAME = "infrahub.webhook.tasks.process"


class _RecordingHTTP:
    """A minimal InfrahubHTTP stand-in that returns a fixed response and records the POST."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.posted: dict[str, object] = {}

    async def post(
        self, url: str, json: object = None, headers: dict[str, str] | None = None, verify: bool | None = None
    ) -> httpx.Response:
        self.posted = {"url": url, "json": json, "headers": headers, "verify": verify}
        return self._response


@pytest.fixture(autouse=True)
def _patch_prefect_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Prefect's get_run_logger with a standard logger so caplog captures output."""
    monkeypatch.setattr(process, "get_run_logger", lambda: logging.getLogger(LOGGER_NAME))


@pytest.fixture(autouse=True)
def _silence_add_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """add_tags only talks to the Prefect runtime; it is irrelevant to these logging tests."""

    async def _noop(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(process, "add_tags", _noop)


@pytest.fixture
def recording_http(monkeypatch: pytest.MonkeyPatch) -> _RecordingHTTP:
    """Stand in for the HTTP service: returns a 200 response and records the POST it received."""
    recorder = _RecordingHTTP(httpx.Response(200, request=httpx.Request("POST", "https://target.example/hook")))
    monkeypatch.setattr(process, "get_http", lambda: recorder)
    return recorder


@pytest.fixture
def resolve_webhook_to(monkeypatch: pytest.MonkeyPatch) -> Callable[[Webhook], None]:
    """Resolve any webhook id to the given webhook, bypassing the cache and the client."""

    def _install(webhook: Webhook) -> None:
        async def _resolve(webhook_id: str, webhook_kind: str) -> Webhook:
            return webhook

        monkeypatch.setattr(process, "_resolve_webhook", _resolve)

    return _install


@pytest.fixture
def webhook_token_env(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set the environment variable that the env-sourced header resolves from; auto-restored afterwards."""
    monkeypatch.setenv("WEBHOOK_TOKEN_ENV", "super-secret-token")
    return "super-secret-token"


async def test_webhook_post_logs_attempt_with_masked_headers_and_payload(
    caplog: pytest.LogCaptureFixture,
    recording_http: _RecordingHTTP,
    webhook_token_env: str,
    resolve_webhook_to: Callable[[Webhook], None],
) -> None:
    # No shared_key: avoids the random webhook-id/timestamp/signature so the logged line is fully fixed.
    webhook = CustomWebhook(
        name="hook",
        url="https://target.example/hook",
        event_type="infrahub.branch.created",
        validate_certificates=False,
        custom_headers=[
            WebhookHeader(key="X-Static", value="plain", kind=HeaderKind.STATIC),
            WebhookHeader(key="X-Token", value="WEBHOOK_TOKEN_ENV", kind=HeaderKind.ENVIRONMENT),
        ],
    )
    resolve_webhook_to(webhook)

    payload = {"event": "branch.created"}
    payload_json = ujson.dumps(payload)
    expected_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Static": "plain",
        "X-Token": "***",
    }

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        await webhook_post.fn(
            webhook_id="id-1", webhook_kind="CustomWebhook", webhook_name="hook", payload=payload, attempt=2
        )

    info_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.INFO]
    debug_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]

    assert info_messages == [
        "Webhook 'hook' attempt 2/4: POST https://target.example/hook "
        f"with headers {expected_headers} and payload {payload_json}"
    ]
    assert debug_messages == [f"Webhook 'hook' attempt 2/4 full payload: {payload_json}"]


async def test_webhook_post_truncates_large_payload_inline_and_logs_it_in_full_at_debug(
    caplog: pytest.LogCaptureFixture,
    recording_http: _RecordingHTTP,
    resolve_webhook_to: Callable[[Webhook], None],
) -> None:
    webhook = CustomWebhook(
        name="hook",
        url="https://target.example/hook",
        event_type="infrahub.branch.created",
        validate_certificates=False,
    )
    resolve_webhook_to(webhook)

    payload = {"blob": "x" * (PAYLOAD_LOG_LIMIT * 2)}
    payload_json = ujson.dumps(payload)
    overflow = len(payload_json) - PAYLOAD_LOG_LIMIT
    truncated = (
        payload_json[:PAYLOAD_LOG_LIMIT] + f"… (+{overflow} characters; enable debug logging for the full payload)"
    )
    expected_headers = {"Accept": "application/json", "Content-Type": "application/json"}

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        await webhook_post.fn(
            webhook_id="id-1", webhook_kind="CustomWebhook", webhook_name="hook", payload=payload, attempt=1
        )

    info_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.INFO]
    debug_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]

    assert info_messages == [
        "Webhook 'hook' attempt 1/4: POST https://target.example/hook "
        f"with headers {expected_headers} and payload {truncated}"
    ]
    assert debug_messages == [f"Webhook 'hook' attempt 1/4 full payload: {payload_json}"]


@dataclass
class FailureLogCase:
    name: str
    run_count: int | None
    location: str  # the attempt phrase in the log line
    retry_note: str  # the trailing retry note, empty when none is expected


@pytest.mark.parametrize(
    "case",
    [
        FailureLogCase(
            name="mid_run_attempt_announces_next_retry",
            run_count=1,
            location="attempt 1/4",
            retry_note=" Retrying in 120s (attempt 2/4).",
        ),
        FailureLogCase(
            name="last_attempt_reports_no_retries_remaining",
            run_count=WEBHOOK_SEND_ATTEMPTS,
            location=f"attempt {WEBHOOK_SEND_ATTEMPTS}/4",
            retry_note=" No retries remaining.",
        ),
        FailureLogCase(
            name="outside_flow_run_omits_attempt_and_retry_note",
            run_count=None,
            location="outside a flow run",
            retry_note="",
        ),
    ],
    ids=lambda case: case.name,
)
async def test_webhook_send_logs_and_raises_the_classified_failure(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, case: FailureLogCase
) -> None:
    monkeypatch.setattr(process.flow_run, "run_count", case.run_count)
    # Pin the clock so the logged elapsed time is a fixed "0 ms" and the line can be matched exactly.
    monkeypatch.setattr(process.time, "monotonic", lambda: 0.0)

    async def _failing_post(**_kwargs: object) -> httpx.Response:
        raise HTTPServerError(message="Connection to https://target.example failed")

    monkeypatch.setattr(process, "webhook_post", _failing_post)

    with (
        caplog.at_level(logging.ERROR, logger=LOGGER_NAME),
        pytest.raises(WebhookDeliveryError, match=r"^Connection to https://target\.example failed$"),
    ):
        await webhook_send.fn(
            webhook_id="id-1", webhook_kind="CustomWebhook", webhook_name="hook", payload={"event": "branch.created"}
        )

    error_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert error_messages == [
        f"Webhook delivery failed [CONNECTION] {case.location} after 0 ms: "
        "Connection to https://target.example failed. "
        f"Verify the target endpoint is reachable from Infrahub.{case.retry_note}"
    ]
