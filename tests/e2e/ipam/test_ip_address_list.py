"""Port of frontend/app/tests/e2e/ipam/ip-address-list.spec.ts.

/ipam/ip_addresses address list: summary view and viewing addresses under a
given prefix (172.16.0.0/16) with breadcrumb navigation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestIpAddressList:
    async def test_view_address_list_and_summary(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam/ip_addresses")

        await page.get_by_test_id("identifier-cell").get_by_role("link", name="10.0.0.16/32").click()

        object_details = page.get_by_test_id("object-details")
        await expect(object_details.get_by_role("heading", name="Details")).to_be_visible()
        await expect(object_details.get_by_text("Address10.0.0.16/32")).to_be_visible()
        await expect(object_details.get_by_text("InterfaceLoopback0")).to_be_visible()
        await expect(object_details.get_by_text("Ip Prefix10.0.0.0/16")).to_be_visible()

        await expect(page.get_by_role("heading", name="Groups")).to_be_visible()
        await expect(page.get_by_role("heading", name="Activities")).to_be_visible()

    async def test_view_all_addresses_under_a_prefix(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")

        # select a prefix to view all ip addresses
        await page.get_by_label("IPAM tree").get_by_text("172.16.0.0/16").click()
        await expect(page.get_by_role("heading", name="172.16.0.0/16")).to_be_visible()
        await page.get_by_role("link", name="IP Addresses").click()

        # click on any ip address row to view summary
        await page.get_by_role("link", name="172.16.0.1/16").click()
        await page.get_by_role("heading", name="172.16.0.1/16").click()
        await page.get_by_role("heading", name="Details").click()
        await page.get_by_role("heading", name="Activities").click()

        # use breadcrumb to go back to parent prefix
        await page.get_by_test_id("breadcrumb-ipam").get_by_role("link", name="172.16.0.0/16").click()
        await expect(page.get_by_role("heading", name="172.16.0.0/16")).to_be_visible()
