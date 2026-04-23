"""Marketplace REST client.

Calls the public Marketplace REST API (``/api/v1/*``) directly via ``httpx``.
Does NOT subprocess ``infrahubctl`` — the backend owns its own HTTP path so it
can run inside a Prefect task, surface structured errors, and honor the
configured ``INFRAHUB_MARKETPLACE_URL`` independently of any user's CLI.

When ``opsmill/infrahub-sdk-python`` exposes a public ``infrahub_sdk.marketplace``
module (the follow-up to PR #952), this file becomes a thin adapter over that
module. Until then, Infrahub owns the client.
"""

from __future__ import annotations

from typing import Any

import httpx

from infrahub import config
from infrahub.log import get_logger

from .models import (
    MarketplaceCollectionDetail,
    MarketplaceCollectionSummary,
    MarketplaceCollectionsListResponse,
    MarketplaceSchemaDetail,
    MarketplaceSchemaSummary,
    MarketplaceSchemasListResponse,
    MarketplaceTagCount,
    MarketplaceTagsResponse,
    MarketplaceVersionContent,
    PageInfo,
)

log = get_logger()

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_BASE_URL = "https://marketplace.infrahub.app"


class MarketplaceUnreachableError(Exception):
    """Raised when the Marketplace upstream is unreachable or returns 5xx."""


class MarketplaceTimeoutError(Exception):
    """Raised when upstream exceeds the configured timeout."""


class MarketplaceNotFoundError(Exception):
    """Raised when upstream returns 404."""


class MarketplaceMisconfiguredError(Exception):
    """Raised when the configured Marketplace URL is invalid."""


def _resolve_base_url(base_url: str | None = None) -> str:
    """Return a cleaned base URL, raising if misconfigured."""
    url = (base_url or config.SETTINGS.marketplace.url or "").strip()
    if not url:
        raise MarketplaceMisconfiguredError("INFRAHUB_MARKETPLACE_URL is not set")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise MarketplaceMisconfiguredError(f"INFRAHUB_MARKETPLACE_URL must use http:// or https:// (got {url!r})")
    return url.rstrip("/")


class MarketplaceClient:
    """Async REST client targeting marketplace.infrahub.app's `/api/v1/*` endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        http: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = _resolve_base_url(base_url)
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> "MarketplaceClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._http.get(url, params=params, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            log.warning("marketplace_timeout", url=url)
            raise MarketplaceTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            log.warning("marketplace_unreachable", url=url, error=str(exc))
            raise MarketplaceUnreachableError(str(exc)) from exc

        if resp.status_code == 404:
            raise MarketplaceNotFoundError(path)
        if resp.status_code >= 500:
            log.warning("marketplace_upstream_5xx", url=url, status=resp.status_code)
            raise MarketplaceUnreachableError(f"Upstream returned {resp.status_code} for {path}")
        if resp.status_code >= 400:
            # 4xx other than 404 — surface upstream detail if present
            detail = "bad_request"
            try:
                detail = resp.json().get("detail", detail)
            except Exception:  # noqa: BLE001
                pass
            raise MarketplaceUnreachableError(f"Upstream 4xx for {path}: {detail}")
        return resp.json()

    async def _get_text(self, path: str) -> tuple[str, httpx.Headers]:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._http.get(url, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise MarketplaceTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise MarketplaceUnreachableError(str(exc)) from exc

        if resp.status_code == 404:
            raise MarketplaceNotFoundError(path)
        if resp.status_code >= 500:
            raise MarketplaceUnreachableError(f"Upstream {resp.status_code} for {path}")
        resp.raise_for_status()
        return resp.text, resp.headers

    # --- List / detail endpoints ---

    async def list_schemas(
        self,
        *,
        search: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        after: str | None = None,
    ) -> MarketplaceSchemasListResponse:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if tags:
            params["tags"] = ",".join(tags)
        if after:
            params["after"] = after
        raw = await self._get_json("/api/v1/schemas", params=params)
        return _parse_schemas_list(raw)

    async def get_schema(self, namespace: str, name: str) -> MarketplaceSchemaDetail:
        raw = await self._get_json(f"/api/v1/schemas/{namespace}/{name}")
        return MarketplaceSchemaDetail.model_validate(raw)

    async def list_collections(
        self,
        *,
        search: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        after: str | None = None,
    ) -> MarketplaceCollectionsListResponse:
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        if tags:
            params["tags"] = ",".join(tags)
        if after:
            params["after"] = after
        raw = await self._get_json("/api/v1/collections", params=params)
        return _parse_collections_list(raw)

    async def get_collection(self, namespace: str, name: str) -> MarketplaceCollectionDetail:
        raw = await self._get_json(f"/api/v1/collections/{namespace}/{name}")
        return MarketplaceCollectionDetail.model_validate(raw)

    async def list_tags(self) -> MarketplaceTagsResponse:
        raw = await self._get_json("/api/v1/tags/counts")
        items = raw.get("items") if isinstance(raw, dict) else raw
        tags = [MarketplaceTagCount.model_validate(item) for item in (items or [])]
        return MarketplaceTagsResponse(tags=tags)

    # --- Content / download endpoints ---

    async def fetch_schema_version_content(self, version_id: str) -> MarketplaceVersionContent:
        raw = await self._get_json(f"/api/v1/schemas/versions/{version_id}/content")
        return MarketplaceVersionContent.model_validate(raw)

    async def fetch_schema_content_by_ref(
        self, namespace: str, name: str, semver: str | None = None
    ) -> tuple[str, str]:
        """Return (yaml_text, resolved_version). Uses `/download` endpoints.

        When semver is None, downloads the latest version.
        """
        if semver:
            path = f"/api/v1/schemas/{namespace}/{name}/versions/{semver}/download"
            resolved = semver
        else:
            path = f"/api/v1/schemas/{namespace}/{name}/download"
            resolved = "latest"
        text, headers = await self._get_text(path)
        resolved = headers.get("x-schema-version", resolved)
        return text, resolved

    async def fetch_collection_bundle(self, namespace: str, name: str) -> dict[str, Any]:
        """Download a collection bundle — a JSON document with embedded schema bodies."""
        raw = await self._get_json(f"/api/v1/collections/{namespace}/{name}/download")
        if not isinstance(raw, dict):
            raise MarketplaceUnreachableError("collection bundle was not a JSON object")
        return raw

    async def ping(self) -> bool:
        try:
            url = f"{self._base_url}/health"
            resp = await self._http.get(url, timeout=2.0)
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False


def _parse_schemas_list(raw: Any) -> MarketplaceSchemasListResponse:
    if not isinstance(raw, dict):
        raise MarketplaceUnreachableError("schemas list was not a JSON object")
    items = [MarketplaceSchemaSummary.model_validate(item) for item in raw.get("items", [])]
    return MarketplaceSchemasListResponse(
        items=items,
        page_info=PageInfo.model_validate(raw.get("page_info", {})),
        total_count=raw.get("total_count", 0),
    )


def _parse_collections_list(raw: Any) -> MarketplaceCollectionsListResponse:
    if not isinstance(raw, dict):
        raise MarketplaceUnreachableError("collections list was not a JSON object")
    items = [MarketplaceCollectionSummary.model_validate(item) for item in raw.get("items", [])]
    return MarketplaceCollectionsListResponse(
        items=items,
        page_info=PageInfo.model_validate(raw.get("page_info", {})),
        total_count=raw.get("total_count", 0),
    )


def make_marketplace_client(http: httpx.AsyncClient | None = None) -> MarketplaceClient:
    """Factory that resolves the URL from Infrahub config at call time."""
    return MarketplaceClient(base_url=None, http=http)
