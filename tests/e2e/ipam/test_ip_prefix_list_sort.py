"""Port of frontend/app/tests/e2e/ipam/ip-prefix-list-sort.spec.ts.

Sort the IPAM root prefix list from the Description column header and
toggle-clear back to the default order. Unlike the TS spec's demo dataset,
the ipam_pools slice creates prefixes without descriptions, so a
description-sorted row order is an implicit uuid tiebreaker — the assertions
pin the URL state, the header indicator, and the restored default first row
rather than a description-driven ordering.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from data.handles import IpamPoolsHandle
    from playwright.async_api import Page


class TestIpPrefixListSorting:
    async def test_sort_prefixes_from_column_header_and_toggle_clear(
        self, page: Page, data_ipam_pools: IpamPoolsHandle
    ) -> None:
        prefix_table = page.get_by_test_id("ip-prefix-table")
        first_row_link = prefix_table.get_by_test_id("data-table-row").first.get_by_role("link").first
        description_header = prefix_table.get_by_role("button", name="Description")

        # navigate and verify the default prefix order
        await page.goto("/ipam")
        await expect(first_row_link).to_have_text("10.0.0.0/8")

        # sort descending from the Description header
        await description_header.click()
        await page.get_by_role("menuitem", name="Sort descending").click()

        await expect(page).to_have_url(re.compile(r"sort=description__value__desc"))
        await expect(prefix_table.get_by_role("button", name="Description sorted descending")).to_be_visible()

        # toggle-clear restores the default order
        await description_header.click()
        await page.get_by_role("menuitem", name="Sort descending").click()

        await expect(page).not_to_have_url(re.compile(r"sort="))
        await expect(first_row_link).to_have_text("10.0.0.0/8")
        await expect(prefix_table.get_by_role("button", name="Description sorted descending")).not_to_be_visible()
