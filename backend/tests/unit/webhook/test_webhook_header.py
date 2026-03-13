import logging
from unittest.mock import patch

import pytest

from infrahub.webhook.models import WebhookHeader


def test_webhook_header_model() -> None:
    """WebhookHeader creation and serialization."""
    header = WebhookHeader(key="Authorization", value="Bearer token123", kind="static")
    assert header.key == "Authorization"
    assert header.value == "Bearer token123"
    assert header.kind == "static"

    dumped = header.model_dump()
    assert dumped == {"key": "Authorization", "value": "Bearer token123", "kind": "static"}
    assert WebhookHeader(**dumped) == header


def test_webhook_header_resolve_static() -> None:
    header = WebhookHeader(key="Authorization", value="Bearer token", kind="static")
    assert header.resolve() == "Bearer token"


def test_webhook_header_resolve_environment() -> None:
    header = WebhookHeader(key="X-API-Key", value="MY_API_KEY", kind="environment")
    with patch.dict("os.environ", {"MY_API_KEY": "secret123"}):
        assert header.resolve() == "secret123"


def test_webhook_header_resolve_missing_environment(caplog: pytest.LogCaptureFixture) -> None:
    header = WebhookHeader(key="X-API-Key", value="MISSING_VAR", kind="environment")
    with patch.dict("os.environ", {}, clear=True), caplog.at_level(logging.WARNING, logger="infrahub.webhook.models"):
        result = header.resolve()

    assert result is None
    assert "MISSING_VAR" in caplog.text
    assert "X-API-Key" in caplog.text
