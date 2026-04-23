from __future__ import annotations

import httpx
import pytest

from infrahub.marketplace.client import (
    MarketplaceClient,
    MarketplaceMisconfiguredError,
    MarketplaceNotFoundError,
    MarketplaceTimeoutError,
    MarketplaceUnreachableError,
    _resolve_base_url,
)


def test_resolve_base_url_strips_trailing_slash() -> None:
    assert _resolve_base_url("https://example.com/") == "https://example.com"


def test_resolve_base_url_accepts_http_and_https() -> None:
    assert _resolve_base_url("http://example.com").startswith("http://")
    assert _resolve_base_url("https://example.com").startswith("https://")


def test_resolve_base_url_rejects_non_http_scheme() -> None:
    with pytest.raises(MarketplaceMisconfiguredError):
        _resolve_base_url("ftp://example.com")


def test_resolve_base_url_rejects_empty() -> None:
    # Passing an explicit empty string bypasses fall-through to config.SETTINGS.
    from infrahub.marketplace import client as client_mod

    class _FakeConfigSettings:
        class _FakeMarketplace:
            url = ""

        marketplace = _FakeMarketplace()

    original = client_mod.config.SETTINGS
    client_mod.config.SETTINGS = _FakeConfigSettings()  # type: ignore[assignment]
    try:
        with pytest.raises(MarketplaceMisconfiguredError):
            _resolve_base_url("")
    finally:
        client_mod.config.SETTINGS = original


class _FakeTransport(httpx.MockTransport):
    def __init__(self, handler) -> None:  # type: ignore[no-untyped-def]
        super().__init__(handler)


@pytest.mark.asyncio
async def test_list_schemas_parses_response() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "s-1",
                        "namespace": "infrahub",
                        "name": "vlan-translation",
                        "display_name": "VLAN Translation",
                        "description": "desc",
                        "visibility": "public",
                        "download_count": 3,
                        "upvote_count": 0,
                        "fork_count": 0,
                        "viewer_has_upvoted": False,
                        "created_at": "2026-04-23T00:00:00Z",
                        "updated_at": "2026-04-23T00:00:00Z",
                        "author": {"id": "a1", "username": "ops", "avatar_url": None},
                        "tags": [{"id": "t1", "name": "network"}],
                        "latest_version": {
                            "id": "v1",
                            "semver": "1.0.0",
                            "status": "published",
                            "changelog": None,
                            "download_count": 0,
                            "download_url": "/api/v1/schemas/infrahub/vlan-translation/versions/1.0.0/download",
                            "created_at": "2026-04-23T00:00:00Z",
                        },
                    }
                ],
                "page_info": {"has_next_page": False, "end_cursor": None},
                "total_count": 1,
            },
        )

    client = MarketplaceClient(
        base_url="https://example.com",
        http=httpx.AsyncClient(transport=_FakeTransport(handler)),
    )
    try:
        result = await client.list_schemas(limit=10)
    finally:
        await client.close()

    assert result.total_count == 1
    assert result.items[0].name == "vlan-translation"
    assert "/api/v1/schemas" in str(calls[0].url)


@pytest.mark.asyncio
async def test_get_schema_404_raises_not_found() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    client = MarketplaceClient(
        base_url="https://example.com",
        http=httpx.AsyncClient(transport=_FakeTransport(handler)),
    )
    try:
        with pytest.raises(MarketplaceNotFoundError):
            await client.get_schema(namespace="nope", name="missing")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_list_schemas_5xx_raises_unreachable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = MarketplaceClient(
        base_url="https://example.com",
        http=httpx.AsyncClient(transport=_FakeTransport(handler)),
    )
    try:
        with pytest.raises(MarketplaceUnreachableError):
            await client.list_schemas()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_ping_timeout_returns_false() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("nope")

    client = MarketplaceClient(
        base_url="https://example.com",
        http=httpx.AsyncClient(transport=_FakeTransport(handler)),
    )
    try:
        assert await client.ping() is False
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_fetch_schema_content_by_ref_uses_version_endpoint() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(
            200,
            text="type: CoreNode\n",
            headers={"x-schema-version": "1.2.0", "content-type": "text/plain"},
        )

    client = MarketplaceClient(
        base_url="https://example.com",
        http=httpx.AsyncClient(transport=_FakeTransport(handler)),
    )
    try:
        text, resolved = await client.fetch_schema_content_by_ref(
            namespace="infrahub", name="foo", semver="1.2.0"
        )
    finally:
        await client.close()
    assert text == "type: CoreNode\n"
    assert resolved == "1.2.0"
    assert "/api/v1/schemas/infrahub/foo/versions/1.2.0/download" in captured[0]


@pytest.mark.asyncio
async def test_fetch_schema_content_by_ref_latest_endpoint() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, text="x: 1\n")

    client = MarketplaceClient(
        base_url="https://example.com",
        http=httpx.AsyncClient(transport=_FakeTransport(handler)),
    )
    try:
        _, resolved = await client.fetch_schema_content_by_ref(
            namespace="infrahub", name="foo", semver=None
        )
    finally:
        await client.close()
    assert resolved == "latest"
    assert "/api/v1/schemas/infrahub/foo/download" in captured[0]


@pytest.mark.asyncio
async def test_client_timeout_raises_timeout_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    client = MarketplaceClient(
        base_url="https://example.com",
        http=httpx.AsyncClient(transport=_FakeTransport(handler)),
    )
    try:
        with pytest.raises(MarketplaceTimeoutError):
            await client.list_schemas()
    finally:
        await client.close()
