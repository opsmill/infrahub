"""Port of frontend/app/tests/e2e/ipam/ip-prefix-list-filters.spec.ts.

Filter the IPAM root prefix list by search text and by the Member Type column.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from data.handles import IpamPoolsHandle
    from playwright.async_api import Page


class TestIpPrefixListFiltering:
    async def test_filter_by_search_text_and_column(self, page: Page, data_ipam_pools: IpamPoolsHandle) -> None:
        await page.goto("/ipam")
        identifier_cell = page.get_by_test_id("identifier-cell")

        # verify initial prefix list
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/8")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/16")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.1.0.0/16")).to_be_visible()

        # filter prefixes by search text
        await page.get_by_placeholder("Search IP Prefix").fill("10.0.0.0/")
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/8")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/16")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.1.0.0/16")).not_to_be_visible()

        # further filter using column filtering
        await page.get_by_role("button", name="Member Type").click()
        await page.get_by_role("option", name="Prefix Prefix serves as").click()
        await page.get_by_role("button", name="Apply").click()
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/8")).to_be_visible()
        await expect(identifier_cell.get_by_role("link", name="10.0.0.0/16")).not_to_be_visible()
