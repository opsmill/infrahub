"""Port of frontend/app/tests/e2e/ipam/sub-ip-prefix-list-filters.spec.ts.

Filter the sub-prefix (Children) list of 10.0.0.0/8 by Member Type and search.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import expect

if TYPE_CHECKING:
    from data.handles import IpamPoolsHandle
    from playwright.async_api import Page


class TestSubIpPrefixListFiltering:
    async def test_filter_sub_prefixes_by_column_and_search(self, page: Page, data_ipam_pools: IpamPoolsHandle) -> None:
        await page.goto("/ipam")
        await page.get_by_test_id("identifier-cell").get_by_role("link", name="10.0.0.0/8").click()
        await page.get_by_role("link", name="Children").click()
        identifier_cell = page.get_by_test_id("identifier-cell")

        # verify initial sub prefix list
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/16")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.1.0.0/16")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.2.0.0/16")).to_be_visible()

        # filter using column filtering
        await page.get_by_role("button", name="Member Type").click()
        await page.get_by_role("option", name="Prefix Prefix serves as").click()
        await page.get_by_role("button", name="Apply").click()
        await expect(identifier_cell.get_by_role("link", name="10.1.0.0/16")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.2.0.0/16")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/16")).not_to_be_visible()

        # add filtering by search text
        await page.get_by_placeholder("Search IP Prefix").fill("10.1")
        await expect(identifier_cell.get_by_role("link", name="10.1.0.0/16")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.2.0.0/16")).not_to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/16")).not_to_be_visible()
