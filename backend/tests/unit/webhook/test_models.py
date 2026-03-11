import logging
import os
from unittest.mock import patch
from uuid import UUID

from infrahub.core.timestamp import Timestamp
from infrahub.webhook.models import HeaderConfig, StandardWebhook


def test_standard_webhook() -> None:
    webhook = StandardWebhook(
        name="test", url="http://test.com", event_type="test", validate_certificates=True, shared_key="test"
    )
    assert webhook.webhook_type == "StandardWebhook"

    cache_dict = {
        "name": "test",
        "url": "http://test.com",
        "event_type": "test",
        "validate_certificates": True,
        "shared_key": "test",
        "custom_headers": [],
        "webhook_type": "StandardWebhook",
    }
    assert webhook.to_cache() == cache_dict

    assert StandardWebhook.from_cache(cache_dict) == webhook


def test_standard_webhook_header() -> None:
    webhook = StandardWebhook(
        name="test", url="http://test.com", event_type="test", validate_certificates=True, shared_key="test"
    )
    test_id = UUID("217b4ebc-b84f-4736-b1ee-222182aed371")
    time1 = Timestamp("2025-02-27T11:43:49.064807Z")
    webhook._assign_headers(uuid=test_id, at=time1)

    assert webhook._headers == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "webhook-id": "msg_217b4ebcb84f4736b1ee222182aed371",
        "webhook-signature": "v1,BQN9AgPA4evuGDChi9VKxNKRwediIXsAQz8hVHMfKNg=",
        "webhook-timestamp": "1740656629",
    }


def test_custom_headers_merged_with_system_defaults() -> None:
    """T009: Verify custom headers merge with system defaults and override on name conflict."""
    headers = [
        HeaderConfig(key="Authorization", value="Bearer token123", header_type="password"),
        HeaderConfig(key="X-Source-System", value="infrahub", header_type="static"),
    ]
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key="test",
        custom_headers=headers,
    )
    webhook._assign_headers()

    assert webhook._headers is not None
    # System defaults present
    assert "webhook-id" in webhook._headers
    assert "webhook-timestamp" in webhook._headers
    assert "webhook-signature" in webhook._headers
    # Custom headers merged
    assert webhook._headers["Authorization"] == "Bearer token123"
    assert webhook._headers["X-Source-System"] == "infrahub"


def test_custom_header_overrides_system_default() -> None:
    """T009: Custom header with same name as system header takes precedence (FR-006)."""
    headers = [
        HeaderConfig(key="Content-Type", value="text/plain", header_type="static"),
    ]
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key=None,
        custom_headers=headers,
    )
    webhook._assign_headers()

    assert webhook._headers is not None
    assert webhook._headers["Content-Type"] == "text/plain"


def test_cache_roundtrip_with_custom_headers() -> None:
    """T010: Verify to_cache() includes headers and from_cache() reconstructs them."""
    headers = [
        HeaderConfig(key="Authorization", value="Bearer secret", header_type="password"),
        HeaderConfig(key="X-Env-Key", value="MY_VAR", header_type="env"),
    ]
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key="key",
        custom_headers=headers,
    )

    cache_data = webhook.to_cache()
    assert len(cache_data["custom_headers"]) == 2
    assert cache_data["custom_headers"][0] == {
        "key": "Authorization",
        "value": "Bearer secret",
        "header_type": "password",
    }

    restored = StandardWebhook.from_cache(cache_data)
    assert restored.custom_headers == headers
    assert restored == webhook


def test_env_var_header_resolved_at_send_time() -> None:
    """T015: Verify env var headers resolve via os.environ.get()."""
    headers = [
        HeaderConfig(key="X-API-Key", value="MY_API_KEY", header_type="env"),
    ]
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key=None,
        custom_headers=headers,
    )
    with patch.dict(os.environ, {"MY_API_KEY": "secret123"}):
        webhook._assign_headers()

    assert webhook._headers is not None
    assert webhook._headers["X-API-Key"] == "secret123"


def test_env_var_header_skipped_when_missing() -> None:
    """T015: Missing env var header is skipped, no exception raised."""
    headers = [
        HeaderConfig(key="X-API-Key", value="NONEXISTENT_VAR", header_type="env"),
        HeaderConfig(key="X-Static", value="present", header_type="static"),
    ]
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key=None,
        custom_headers=headers,
    )
    with patch.dict(os.environ, {}, clear=False):
        # Ensure the var is NOT set
        os.environ.pop("NONEXISTENT_VAR", None)
        webhook._assign_headers()

    assert webhook._headers is not None
    assert "X-API-Key" not in webhook._headers
    assert webhook._headers["X-Static"] == "present"


def test_env_var_missing_logs_warning(caplog: logging.LogRecord) -> None:
    """T016: Warning logged with missing variable name when env var not set."""
    headers = [
        HeaderConfig(key="X-Secret", value="MISSING_SECRET_VAR", header_type="env"),
    ]
    webhook = StandardWebhook(
        name="test-webhook",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key=None,
        custom_headers=headers,
    )
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MISSING_SECRET_VAR", None)
        with caplog.at_level(logging.WARNING, logger="infrahub.webhook"):
            webhook._assign_headers()

    assert any("MISSING_SECRET_VAR" in record.message for record in caplog.records)


def test_static_header_value_used_directly() -> None:
    """T022: Static key-value header value is used as-is (not masked)."""
    headers = [
        HeaderConfig(key="X-Source-System", value="infrahub", header_type="static"),
        HeaderConfig(key="X-Tenant-Id", value="acme-corp", header_type="static"),
    ]
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key=None,
        custom_headers=headers,
    )
    webhook._assign_headers()

    assert webhook._headers is not None
    assert webhook._headers["X-Source-System"] == "infrahub"
    assert webhook._headers["X-Tenant-Id"] == "acme-corp"
