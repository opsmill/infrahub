"""Port of frontend/app/tests/e2e/request-priority.spec.ts.

Every frontend-emitted request to the Infrahub API must carry the
``X-Priority: high`` header so server-side admission control can favor
interactive traffic under load (the middleware itself is covered by
backend/tests/component/api/test_admission_middleware.py; this test pins the
frontend half of the contract). Drives one interactive navigation as admin and
asserts the header on every same-origin ``/graphql`` and ``/api`` request.
Relies on the seeded ``blue`` tag (data_org_registry) for a data-backed page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from data.handles import OrgRegistryHandle
    from playwright.async_api import Page, Request


@dataclass
class CapturedRequest:
    url: str
    method: str
    # Playwright lowercases request-header names, so the observed key is
    # `x-priority` even though the wire header is title-cased `X-Priority`.
    priority: str | None


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _is_infrahub_api_request(request: CapturedRequest, app_origin: str) -> bool:
    """Whether this is a frontend-emitted request to the Infrahub API.

    Same origin as the app, on a transport path (``/graphql`` or ``/api/``).
    Excludes static assets, the app document, external hosts, and CORS
    preflights (which never carry the header).
    """
    if request.method == "OPTIONS":
        return False
    if _origin(request.url) != app_origin:
        return False
    return urlsplit(request.url).path.startswith(("/graphql", "/api/"))


class TestRequestPriority:
    async def test_interactive_flow_emits_x_priority_high_on_every_api_request(
        self, admin_page: Page, data_org_registry: OrgRegistryHandle
    ) -> None:
        captured: list[CapturedRequest] = []

        def _capture(request: Request) -> None:
            captured.append(
                CapturedRequest(
                    url=request.url,
                    method=request.method,
                    priority=request.headers.get("x-priority"),
                )
            )

        admin_page.on("request", _capture)

        # drive an interactive navigation
        await admin_page.goto("/objects/BuiltinTag")
        await expect(admin_page.get_by_role("link", name="blue")).to_be_visible()

        # assert every Infrahub-API request carried X-Priority: high
        app_origin = _origin(admin_page.url)
        api_requests = [request for request in captured if _is_infrahub_api_request(request, app_origin)]

        assert api_requests, "expected at least one Infrahub-API request during the navigation"
        offenders = [
            f"{request.method} {request.url} -> {request.priority!r}"
            for request in api_requests
            if request.priority != "high"
        ]
        assert not offenders, f"no frontend API request may be normal, low, or unheadered: {offenders}"
