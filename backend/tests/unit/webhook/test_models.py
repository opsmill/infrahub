from uuid import UUID

from infrahub.core.timestamp import Timestamp
from infrahub.webhook.models import CustomWebhook, StandardWebhook, WebhookHeader


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
    webhook._assign_headers(uuid=test_id, at=time1)

    assert webhook._headers == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "webhook-id": "msg_217b4ebcb84f4736b1ee222182aed371",
        "webhook-signature": "v1,BQN9AgPA4evuGDChi9VKxNKRwediIXsAQz8hVHMfKNg=",
        "webhook-timestamp": "1740656629",
    }


def test_webhook_header_model() -> None:
    """WebhookHeader creation and serialization."""
    header = WebhookHeader(key="Authorization", value="Bearer token123", kind="static")
    assert header.key == "Authorization"
    assert header.value == "Bearer token123"
    assert header.kind == "static"

    dumped = header.model_dump()
    assert dumped == {"key": "Authorization", "value": "Bearer token123", "kind": "static"}
    assert WebhookHeader(**dumped) == header


def test_assign_headers_with_static_custom_header() -> None:
    """_assign_headers() with static custom header."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[WebhookHeader(key="Authorization", value="Bearer token", kind="static")],
    )
    webhook._assign_headers()

    assert webhook._headers is not None
    assert webhook._headers["Authorization"] == "Bearer token"
    assert webhook._headers["Accept"] == "application/json"
    assert webhook._headers["Content-Type"] == "application/json"


def test_custom_header_overrides_default() -> None:
    """Custom header overrides default header."""
    webhook = CustomWebhook(
        name="test",
        url="http://test.com",
        event_type="test",
        validate_certificates=True,
        custom_headers=[WebhookHeader(key="Content-Type", value="text/plain", kind="static")],
    )
    webhook._assign_headers()

    assert webhook._headers is not None
    assert webhook._headers["Content-Type"] == "text/plain"


def test_cache_roundtrip_preserves_custom_headers() -> None:
    """to_cache()/from_cache() roundtrip preserves custom_headers."""
    headers = [
        WebhookHeader(key="X-Source", value="infrahub", kind="static"),
        WebhookHeader(key="Y-Source", value="opsmill", kind="static"),
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
    webhook._payload = {
        "data": {"id": "abc123", "kind": "BuiltinTag", "display_label": "my tag"},
        "event_type": "infrahub.node.created",
        "branch": "main",
    }
    test_id = UUID("217b4ebc-b84f-4736-b1ee-222182aed371")
    time1 = Timestamp("2025-02-27T11:43:49.064807Z")
    webhook._assign_headers(uuid=test_id, at=time1)

    assert webhook._headers == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "webhook-id": "msg_217b4ebcb84f4736b1ee222182aed371",
        "webhook-timestamp": "1740656629",
        "webhook-signature": "v1,5JQxZW3lMNdaSnofcSV0Y3krxQ7aZI7EyThUqHVDGc4=",
    }
