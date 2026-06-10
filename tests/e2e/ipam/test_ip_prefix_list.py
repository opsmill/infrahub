"""Port of frontend/app/tests/e2e/ipam/ip-prefix-list.spec.ts.

/ipam/ip_prefixes prefix list: summary view, sub-prefix navigation, error pages
for unknown schema/id, and text search. Runs anonymously against the IP tree
seeded by data_sites (the 203.111.0.0/16 utilization; 10.0.0.0/8 and the
2001:db8::/100 IPv6 tree via its ipam_pools dependency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import expect

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestIpPrefixList:
    async def test_view_prefix_list_and_summary(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")
        await (
            page.get_by_test_id("ip-prefix-table")
            .get_by_test_id("identifier-cell")
            .get_by_role("link", name="203.111.0.0/16")
            .click()
        )
        await page.get_by_role("link", name="Details").click()
        object_details = page.get_by_test_id("object-details")
        await expect(object_details.get_by_role("heading", name="Details")).to_be_visible()
        await expect(object_details.get_by_text("Prefix203.111.0.0/16")).to_be_visible()
        await expect(object_details.get_by_text("Utilization0%")).to_be_visible()
        await expect(object_details.get_by_role("progressbar")).to_be_visible()
        await expect(object_details.get_by_text("IP Namespacedefault")).to_be_visible()
        await expect(page.get_by_role("heading", name="Groups")).to_be_visible()
        await expect(page.get_by_role("heading", name="Activities")).to_be_visible()

    async def test_view_all_sub_prefixes(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")

        # select a prefix to view all sub prefixes
        await page.get_by_label("IPAM tree").get_by_text("2001:db8::/100").click()
        await expect(page.get_by_role("heading", name="2001:db8::/100")).to_be_visible()
        await expect(page.get_by_test_id("ip-prefix-table")).to_be_visible()

        # go to any sub prefix list of any children prefix
        await page.get_by_role("link", name="2001:db8::/110").click()
        await expect(page.get_by_role("heading", name="2001:db8::/110")).to_be_visible()
        await expect(page.get_by_test_id("ip-address-table")).to_be_visible()

        # use breadcrumb to go back to parent prefix
        await page.get_by_test_id("breadcrumb-ipam").get_by_role("link", name="2001:db8::/100").click()
        await expect(page.get_by_role("heading", name="2001:db8::/100")).to_be_visible()

    async def test_error_when_schema_not_found(self, page: Page, schema_base: None) -> None:
        await page.goto("/ipam/IpamIPPrefix/YYY")
        await expect(page.get_by_text("Cannot find IP Prefix with id YYY")).to_be_visible()

    async def test_error_when_prefix_id_not_found(self, page: Page) -> None:
        await page.goto("/ipam/XXX/YYY")
        await expect(page.get_by_text("Schema for XXX not found.")).to_be_visible()

    async def test_search_prefixes_using_text_search(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")
        await expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("10.0.0.0/8")

        # enter search term and verify filtered results
        await page.get_by_test_id("object-list-search-bar").get_by_role("searchbox", name="Search").fill("2001")
        await expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("2001:db8::/100")
        await expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("2001:db8::14:0/110")
        await expect(page.get_by_test_id("ip-prefix-table")).not_to_contain_text("10.0.0.0/8")

        # clear search and verify all results return
        await page.get_by_role("button", name="Clear filters").click()
        await expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("10.0.0.0/8")
