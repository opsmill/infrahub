"""Port of frontend/app/tests/e2e/menu/menu-view.spec.ts.

Sidebar menu: open the Location menu group. Also fails the test on any HTTP 500
response (a regression guard). Needs the navigation menu loaded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from helpers import save_screenshot_for_docs

if TYPE_CHECKING:
    from playwright.async_api import Page, Response


class TestMenuView:
    async def test_reach_location_menu(self, admin_page: Page, infrastructure_menu: None) -> None:
        # Regression guard: fail if any response is a 500 (mirrors the TS beforeEach).
        server_errors: list[str] = []

        def _record_500(response: Response) -> None:
            if response.status == 500:
                server_errors.append(response.url)

        admin_page.on("response", _record_500)

        await admin_page.goto("/")
        await admin_page.get_by_test_id("sidebar").get_by_role("button", name="Location").click()
        admin_page.get_by_role("menu", name="Location")
        await save_screenshot_for_docs(admin_page, "location_menu")

        assert not server_errors, f"Unexpected 500 responses: {server_errors}"
