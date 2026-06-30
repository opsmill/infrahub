import logging
from unittest.mock import patch
from uuid import UUID

import pytest

from infrahub.core.timestamp import Timestamp
from infrahub.webhook.models import (
    MASKED_HEADER_VALUE,
    CustomWebhook,
    HeaderKind,
    StandardWebhook,
    WebhookHeader,
    WebhookHeaderResolutionError,
)


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
        "custom_headers": [],
        "shared_key": "test",
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
    headers = webhook.build_headers(payload=None, uuid=test_id, at=time1)

    assert headers == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "webhook-id": "msg_217b4ebcb84f4736b1ee222182aed371",
        "webhook-signature": "v1,BQN9AgPA4evuGDChi9VKxNKRwediIXsAQz8hVHMfKNg=",
        "webhook-timestamp": "1740656629",
    }


def test_build_headers_with_static_custom_header() -> None:
    """Static custom header is added alongside the default headers."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[WebhookHeader(key="Authorization", value="Bearer token", kind=HeaderKind.STATIC)],
    )
    headers = webhook.build_headers(payload=None)

    assert headers["Authorization"] == "Bearer token"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"


def test_custom_header_overrides_default() -> None:
    """Custom header overrides default header."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[WebhookHeader(key="Content-Type", value="text/plain", kind=HeaderKind.STATIC)],
    )
    headers = webhook.build_headers(payload=None)

    assert headers["Content-Type"] == "text/plain"


def test_cache_roundtrip_preserves_custom_headers() -> None:
    """to_cache()/from_cache() roundtrip preserves custom_headers."""
    headers = [
        WebhookHeader(key="X-Source", value="infrahub", kind=HeaderKind.STATIC),
        WebhookHeader(key="Y-Source", value="opsmill", kind=HeaderKind.STATIC),
    ]
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key="key123",
        custom_headers=headers,
    )

    cache_data = webhook.to_cache()
    restored = StandardWebhook.from_cache(cache_data)

    assert restored.custom_headers == headers
    assert len(restored.custom_headers) == 2
    assert restored.custom_headers[0].key == "X-Source"
    assert restored.custom_headers[0].kind == "static"


def test_build_headers_resolves_environment_variable() -> None:
    """Environment variable header resolves from os.environ at send time."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[WebhookHeader(key="X-API-Key", value="MY_API_KEY", kind=HeaderKind.ENVIRONMENT)],
    )

    with patch.dict("os.environ", {"MY_API_KEY": "secret123"}):
        headers = webhook.build_headers(payload=None)

    assert headers["X-API-Key"] == "secret123"
    assert headers["Accept"] == "application/json"


def test_build_headers_fails_on_missing_environment_variable(cleared_environment: None) -> None:
    """A missing environment-sourced header fails the delivery instead of being silently skipped."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[
            WebhookHeader(key="X-API-Key", value="MISSING_VAR", kind=HeaderKind.ENVIRONMENT),
            WebhookHeader(key="X-Source", value="infrahub", kind=HeaderKind.STATIC),
        ],
    )

    with pytest.raises(
        WebhookHeaderResolutionError,
        match=r"^Webhook 'test': could not resolve header 'X-API-Key': Environment variable 'MISSING_VAR' not found$",
    ):
        webhook.build_headers(payload=None)


def test_build_headers_warns_on_duplicate_keys(caplog: pytest.LogCaptureFixture) -> None:
    """Duplicate header keys produce a warning and the last value wins."""
    webhook = CustomWebhook(
        name="dup-test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[
            WebhookHeader(key="X-Token", value="first", kind=HeaderKind.STATIC),
            WebhookHeader(key="X-Token", value="second", kind=HeaderKind.STATIC),
        ],
    )

    with caplog.at_level(logging.WARNING, logger="infrahub.webhook.models"):
        headers = webhook.build_headers(payload=None)

    assert headers["X-Token"] == "second"
    assert "duplicate header key 'X-Token'" in caplog.text
    assert "dup-test" in caplog.text


def test_webhook_signature_with_payload() -> None:
    """Signature is computed on compact JSON of the payload, not str(dict) or spaced JSON.

    Hardcoded expected value catches regressions if the serialization format changes.
    """
    webhook = StandardWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        shared_key="my-webhook-secret",
    )
    payload = {
        "data": {"id": "abc123", "kind": "BuiltinTag", "display_label": "my tag"},
        "event_type": "infrahub.node.created",
        "branch": "main",
    }
    test_id = UUID("217b4ebc-b84f-4736-b1ee-222182aed371")
    time1 = Timestamp("2025-02-27T11:43:49.064807Z")
    headers = webhook.build_headers(payload=payload, uuid=test_id, at=time1)

    assert headers == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "webhook-id": "msg_217b4ebcb84f4736b1ee222182aed371",
        "webhook-timestamp": "1740656629",
        "webhook-signature": "v1,5JQxZW3lMNdaSnofcSV0Y3krxQ7aZI7EyThUqHVDGc4=",
    }


def test_redact_headers_masks_environment_value_and_signature() -> None:
    """Environment-sourced values and the signature are masked; everything else stays verbatim."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[
            WebhookHeader(key="X-Static", value="plain", kind=HeaderKind.STATIC),
            WebhookHeader(key="Authorization", value="SECRET_TOKEN", kind=HeaderKind.ENVIRONMENT),
        ],
    )
    headers = {
        "Accept": "application/json",
        "X-Static": "plain",
        "Authorization": "resolved-secret-value",
        "webhook-id": "msg_1",
        "webhook-timestamp": "1740656629",
        "webhook-signature": "v1,c2lnbmF0dXJl",
    }

    redacted = webhook.redact_headers(headers)

    assert redacted == {
        "Accept": "application/json",
        "X-Static": "plain",
        "Authorization": MASKED_HEADER_VALUE,
        "webhook-id": "msg_1",
        "webhook-timestamp": "1740656629",
        "webhook-signature": MASKED_HEADER_VALUE,
    }
    assert headers["Authorization"] == "resolved-secret-value"  # the source mapping is left untouched


def test_redact_headers_without_sensitive_headers_returns_equal_copy() -> None:
    """With no environment header and no signature, nothing is masked."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[WebhookHeader(key="X-Static", value="plain", kind=HeaderKind.STATIC)],
    )
    headers = {"Accept": "application/json", "X-Static": "plain"}

    redacted = webhook.redact_headers(headers)

    assert redacted == headers
    assert redacted is not headers
