"""Port of frontend/app/tests/e2e/objects/list/object-list-search.spec.ts.

Object list search: type in the per-kind search box on the InfraDevice list and
verify the result set narrows. Runs as Admin against main (no branch), hence the
data_sites dependency (the demo devices atl1-core1/atl1-edge1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestObjectListSearch:
    async def test_verify_the_search(self, admin_page: Page, data_sites: SitesHandle) -> None:
        await admin_page.goto("/objects/InfraDevice")

        # initial state
        await expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="atl1-edge1")).to_be_visible()

        # should search an object and verify the total amount of results
        await admin_page.get_by_placeholder("Search Device").fill("core1")

        await expect(admin_page.get_by_role("link", name="atl1-core1")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="atl1-edge1")).not_to_be_visible()
