import json

import httpx


def test_httpx_json_serialization_matches_signature_format() -> None:
    """Guard against httpx changing its JSON serialization.

    The webhook signature is computed over compact JSON (no spaces).
    If httpx ever changes its serializer this test will break before.
    """
    payload = {
        "data": {"id": "abc123", "kind": "BuiltinTag", "display_label": "my tag"},
        "event_type": "infrahub.node.created",
        "branch": "main",
    }

    # What our signature code signs (compact JSON, deterministic key order)
    signed_body = json.dumps(payload, separators=(",", ":")).encode()

    # What httpx will actually put on the wire
    request = httpx.Request("POST", "http://test.com", json=payload)
    httpx_body = request.content

    assert httpx_body == signed_body, (
        f"httpx JSON serialization diverged from compact json.dumps.\n"
        f"  signed : {signed_body!r}\n"
        f"  httpx  : {httpx_body!r}\n"
        "Webhook receivers will reject signatures if these differ."
    )
