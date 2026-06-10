"""Port of frontend/app/tests/e2e/ipam/ip-address-list.spec.ts.

/ipam/ip_addresses address list: summary view and viewing addresses under a
given prefix (172.16.0.0/16) with breadcrumb navigation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.sync_api import Page


class TestIpAddressList:
    def test_view_address_list_and_summary(self, page: Page, data_sites: SitesHandle) -> None:
        page.goto("/ipam/ip_addresses")

        page.get_by_test_id("identifier-cell").get_by_role("link", name="10.0.0.16/32").click()

        object_details = page.get_by_test_id("object-details")
        expect(object_details.get_by_role("heading", name="Details")).to_be_visible()
        expect(object_details.get_by_text("Address10.0.0.16/32")).to_be_visible()
        expect(object_details.get_by_text("InterfaceLoopback0")).to_be_visible()
        expect(object_details.get_by_text("Ip Prefix10.0.0.0/16")).to_be_visible()

        expect(page.get_by_role("heading", name="Groups")).to_be_visible()
        expect(page.get_by_role("heading", name="Activities")).to_be_visible()

    def test_view_all_addresses_under_a_prefix(self, page: Page, data_sites: SitesHandle) -> None:
        page.goto("/ipam")

        # select a prefix to view all ip addresses
        page.get_by_label("IPAM tree").get_by_text("172.16.0.0/16").click()
        expect(page.get_by_role("heading", name="172.16.0.0/16")).to_be_visible()
        page.get_by_role("link", name="IP Addresses").click()

        # click on any ip address row to view summary
        page.get_by_role("link", name="172.16.0.1/16").click()
        page.get_by_role("heading", name="172.16.0.1/16").click()
        page.get_by_role("heading", name="Details").click()
        page.get_by_role("heading", name="Activities").click()

        # use breadcrumb to go back to parent prefix
        page.get_by_test_id("breadcrumb-ipam").get_by_role("link", name="172.16.0.0/16").click()
        expect(page.get_by_role("heading", name="172.16.0.0/16")).to_be_visible()
