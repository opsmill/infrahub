from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx
import pytest
import ujson

from infrahub.exceptions import HTTPServerError
from infrahub.webhook.classifier import WebhookDeliveryError
from infrahub.webhook.models import CustomWebhook, HeaderKind, WebhookHeader
from infrahub.webhook.tasks import process
from infrahub.webhook.tasks.process import PAYLOAD_LOG_LIMIT, webhook_post, webhook_send

if TYPE_CHECKING:
    from collections.abc import Iterator

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
def _patch_prefect_logger() -> Iterator[None]:
    """Replace Prefect's get_run_logger with a standard logger so caplog captures output."""
    with patch("infrahub.webhook.tasks.process.get_run_logger", return_value=logging.getLogger(LOGGER_NAME)):
        yield


@pytest.fixture(autouse=True)
def _silence_add_tags() -> Iterator[None]:
    """add_tags only talks to the Prefect runtime; it is irrelevant to these logging tests."""

    async def _noop(**_kwargs: object) -> None:
        return None

    with patch.object(process, "add_tags", _noop):
        yield


@pytest.fixture
def recording_http() -> Iterator[_RecordingHTTP]:
    """Stand in for the HTTP service: returns a 200 response and records the POST it received."""
    recorder = _RecordingHTTP(httpx.Response(200, request=httpx.Request("POST", "https://target.example/hook")))
    with patch.object(process, "get_http", return_value=recorder):
        yield recorder


@pytest.fixture
def webhook_token_env() -> Iterator[str]:
    """Set the environment variable that the env-sourced header resolves from, and clear it afterwards."""
    os.environ["WEBHOOK_TOKEN_ENV"] = "super-secret-token"
    yield "super-secret-token"
    os.environ.pop("WEBHOOK_TOKEN_ENV", None)


async def test_webhook_post_logs_attempt_with_masked_headers_and_payload(
    caplog: pytest.LogCaptureFixture, recording_http: _RecordingHTTP, webhook_token_env: str
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

    async def _resolve(webhook_id: str, webhook_kind: str) -> CustomWebhook:
        return webhook

    payload = {"event": "branch.created"}
    payload_json = ujson.dumps(payload)
    expected_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Static": "plain",
        "X-Token": "***",
    }

    with patch.object(process, "_resolve_webhook", _resolve), caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
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
    caplog: pytest.LogCaptureFixture, recording_http: _RecordingHTTP
) -> None:
    webhook = CustomWebhook(
        name="hook",
        url="https://target.example/hook",
        event_type="infrahub.branch.created",
        validate_certificates=False,
    )

    async def _resolve(webhook_id: str, webhook_kind: str) -> CustomWebhook:
        return webhook

    payload = {"blob": "x" * (PAYLOAD_LOG_LIMIT * 2)}
    payload_json = ujson.dumps(payload)
    overflow = len(payload_json) - PAYLOAD_LOG_LIMIT
    truncated = (
        payload_json[:PAYLOAD_LOG_LIMIT] + f"… (+{overflow} characters; enable debug logging for the full payload)"
    )
    expected_headers = {"Accept": "application/json", "Content-Type": "application/json"}

    with patch.object(process, "_resolve_webhook", _resolve), caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
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


async def test_webhook_send_logs_and_raises_the_classified_failure(caplog: pytest.LogCaptureFixture) -> None:
    async def _failing_post(**_kwargs: object) -> httpx.Response:
        raise HTTPServerError(message="Connection to https://target.example failed")

    with (
        patch.object(process, "webhook_post", _failing_post),
        caplog.at_level(logging.ERROR, logger=LOGGER_NAME),
        pytest.raises(WebhookDeliveryError, match=r"^Connection to https://target\.example failed$"),
    ):
        await webhook_send.fn(
            webhook_id="id-1", webhook_kind="CustomWebhook", webhook_name="hook", payload={"event": "branch.created"}
        )

    error_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert len(error_messages) == 1
    # The elapsed milliseconds are the only variable part of the line.
    assert re.fullmatch(
        r"Webhook delivery failed \[CONNECTION\] on attempt 1/4 after \d+ ms: "
        r"Connection to https://target\.example failed\. "
        r"Verify the target endpoint is reachable from Infrahub\.",
        error_messages[0],
    )
