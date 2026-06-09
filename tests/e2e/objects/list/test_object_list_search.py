"""Port of frontend/app/tests/e2e/objects/list/object-list-search.spec.ts.

Object list search: type in the per-kind search box on the InfraDevice list and
verify the result set narrows. Runs as Admin against main (no branch), which
carries the demo devices (atl1-core1/atl1-edge1), hence the infrastructure_data
dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestObjectListSearch:
    def test_verify_the_search(self, admin_page: Page, infrastructure_data: None) -> None:
        admin_page.goto("/objects/InfraDevice")

        # initial state
        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()

        # should search an object and verify the total amount of results
        admin_page.get_by_placeholder("Search Device").fill("core1")

        expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        expect(admin_page.get_by_role("link", name="atl1-edge1")).not_to_be_visible()
