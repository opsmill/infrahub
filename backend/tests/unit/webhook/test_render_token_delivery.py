from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from infrahub.artifacts.render_token import RenderTokenClaims, RenderTokenRequest, validate_render_token
from infrahub.webhook.models import StandardWebhook, Webhook
from infrahub.webhook.tasks import process
from infrahub.webhook.tasks.process import render_request_from_event, webhook_post

LOGGER_NAME = "infrahub.webhook.tasks.process"
RENDER_REQUESTED = "infrahub.artifact.render_requested"


class _RecordingHTTP:
    def __init__(self) -> None:
        self.posted: dict[str, object] = {}

    async def post(
        self, url: str, json: object = None, headers: dict[str, str] | None = None, verify: bool | None = None
    ) -> httpx.Response:
        self.posted = {"url": url, "json": json, "headers": headers}
        return httpx.Response(200, request=httpx.Request("POST", url))


@pytest.fixture(autouse=True)
def _patch_prefect_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "get_run_logger", lambda: logging.getLogger(LOGGER_NAME))


@pytest.fixture
def recording_http(monkeypatch: pytest.MonkeyPatch) -> _RecordingHTTP:
    recorder = _RecordingHTTP()
    monkeypatch.setattr(process, "get_http", lambda: recorder)
    return recorder


def _use_webhook(monkeypatch: pytest.MonkeyPatch, webhook: Webhook) -> None:
    async def _resolve(webhook_id: str, webhook_kind: str) -> Webhook:
        return webhook

    monkeypatch.setattr(process, "_resolve_webhook", _resolve)


def _webhook(shared_key: str | None = None) -> StandardWebhook:
    return StandardWebhook(
        name="engine",
        url="https://engine.example/render",
        event_type=RENDER_REQUESTED,
        validate_certificates=False,
        shared_key=shared_key,
    )


def _render_request() -> RenderTokenRequest:
    return RenderTokenRequest(
        render_id="render-1",
        artifact_id="artifact-1",
        branch="main",
        deadline=datetime.now(tz=UTC) + timedelta(hours=1),
    )


async def test_render_requested_delivery_adds_a_token_header_for_the_render(
    monkeypatch: pytest.MonkeyPatch, recording_http: _RecordingHTTP
) -> None:
    _use_webhook(monkeypatch, _webhook())

    await webhook_post(
        webhook_id="id-1",
        webhook_kind="CoreStandardWebhook",
        webhook_name="engine",
        payload={"event": RENDER_REQUESTED, "data": {"render_id": "render-1"}},
        attempt=1,
        render_request=_render_request(),
    )

    headers = recording_http.posted["headers"]
    assert isinstance(headers, dict)
    assert validate_render_token(headers["X-Infrahub-Render-Token"]) == RenderTokenClaims(
        render_id="render-1", artifact_id="artifact-1", branch="main"
    )


async def test_placeholder_in_the_body_is_replaced_and_signed_but_never_logged(
    monkeypatch: pytest.MonkeyPatch, recording_http: _RecordingHTTP, caplog: pytest.LogCaptureFixture
) -> None:
    _use_webhook(monkeypatch, _webhook(shared_key="shared-secret"))
    payload = {"extra_vars": {"token": "${INFRAHUB_RENDER_TOKEN}", "render_id": "render-1"}}

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        await webhook_post(
            webhook_id="id-1",
            webhook_kind="CoreStandardWebhook",
            webhook_name="engine",
            payload=payload,
            attempt=1,
            render_request=_render_request(),
        )

    headers = recording_http.posted["headers"]
    assert isinstance(headers, dict)
    token = headers["X-Infrahub-Render-Token"]
    sent = recording_http.posted["json"]
    assert sent == {"extra_vars": {"token": token, "render_id": "render-1"}}
    assert payload == {"extra_vars": {"token": "${INFRAHUB_RENDER_TOKEN}", "render_id": "render-1"}}

    signed = f"{headers['webhook-id']}.{headers['webhook-timestamp']}.{json.dumps(sent, separators=(',', ':'))}"
    expected_signature = hmac.new(b"shared-secret", signed.encode(), hashlib.sha256).digest()
    assert headers["webhook-signature"] == f"v1,{base64.b64encode(expected_signature).decode()}"

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 2
    assert all(token not in message for message in messages)
    assert all("${INFRAHUB_RENDER_TOKEN}" in message for message in messages)
    assert "  X-Infrahub-Render-Token: ***" in messages[0]


async def test_other_deliveries_carry_no_token(monkeypatch: pytest.MonkeyPatch, recording_http: _RecordingHTTP) -> None:
    _use_webhook(monkeypatch, _webhook())
    payload = {"event": "infrahub.branch.created", "data": {"note": "${INFRAHUB_RENDER_TOKEN}"}}

    await webhook_post(
        webhook_id="id-1", webhook_kind="CoreStandardWebhook", webhook_name="engine", payload=payload, attempt=1
    )

    assert recording_http.posted["json"] == {
        "event": "infrahub.branch.created",
        "data": {"note": "${INFRAHUB_RENDER_TOKEN}"},
    }
    assert recording_http.posted["headers"] == {"Accept": "application/json", "Content-Type": "application/json"}


def test_render_request_is_read_only_from_render_requested_events() -> None:
    event_data = {
        "render_id": "render-1",
        "artifact_id": "artifact-1",
        "branch": "main",
        "deadline": "2026-11-20T10:00:00+00:00",
        "query_result": {"device": {"name": "edge-1"}},
    }

    assert render_request_from_event(event_type=RENDER_REQUESTED, event_data=event_data) == RenderTokenRequest(
        render_id="render-1",
        artifact_id="artifact-1",
        branch="main",
        deadline=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
    )
    assert render_request_from_event(event_type="infrahub.artifact.created", event_data=event_data) is None
