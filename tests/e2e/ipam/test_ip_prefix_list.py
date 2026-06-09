"""Port of frontend/app/tests/e2e/ipam/ip-prefix-list.spec.ts.

/ipam/ip_prefixes prefix list: summary view, sub-prefix navigation, error pages
for unknown schema/id, and text search. Runs anonymously against the demo IP
tree (10.0.0.0/8, 203.111.0.0/16, 2001:db8::/100 ...).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestIpPrefixList:
    def test_view_prefix_list_and_summary(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/ipam")
        page.get_by_test_id("ip-prefix-table").get_by_test_id("identifier-cell").get_by_role(
            "link", name="203.111.0.0/16"
        ).click()
        page.get_by_role("link", name="Details").click()
        object_details = page.get_by_test_id("object-details")
        expect(object_details.get_by_role("heading", name="Details")).to_be_visible()
        expect(object_details.get_by_text("Prefix203.111.0.0/16")).to_be_visible()
        expect(object_details.get_by_text("Utilization0%")).to_be_visible()
        expect(object_details.get_by_role("progressbar")).to_be_visible()
        expect(object_details.get_by_text("IP Namespacedefault")).to_be_visible()
        expect(page.get_by_role("heading", name="Groups")).to_be_visible()
        expect(page.get_by_role("heading", name="Activities")).to_be_visible()

    def test_view_all_sub_prefixes(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/ipam")

        # select a prefix to view all sub prefixes
        page.get_by_label("IPAM tree").get_by_text("2001:db8::/100").click()
        expect(page.get_by_role("heading", name="2001:db8::/100")).to_be_visible()
        expect(page.get_by_test_id("ip-prefix-table")).to_be_visible()

        # go to any sub prefix list of any children prefix
        page.get_by_role("link", name="2001:db8::/110").click()
        expect(page.get_by_role("heading", name="2001:db8::/110")).to_be_visible()
        expect(page.get_by_test_id("ip-address-table")).to_be_visible()

        # use breadcrumb to go back to parent prefix
        page.get_by_test_id("breadcrumb-ipam").get_by_role("link", name="2001:db8::/100").click()
        expect(page.get_by_role("heading", name="2001:db8::/100")).to_be_visible()

    def test_error_when_schema_not_found(self, page: Page, schema_base: None) -> None:
        page.goto("/ipam/IpamIPPrefix/YYY")
        expect(page.get_by_text("Cannot find IP Prefix with id YYY")).to_be_visible()

    def test_error_when_prefix_id_not_found(self, page: Page) -> None:
        page.goto("/ipam/XXX/YYY")
        expect(page.get_by_text("Schema for XXX not found.")).to_be_visible()

    def test_search_prefixes_using_text_search(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/ipam")
        expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("10.0.0.0/8")

        # enter search term and verify filtered results
        page.get_by_test_id("object-list-search-bar").get_by_role("searchbox", name="Search").fill("2001")
        expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("2001:db8::/100")
        expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("2001:db8::14:0/110")
        expect(page.get_by_test_id("ip-prefix-table")).not_to_contain_text("10.0.0.0/8")

        # clear search and verify all results return
        page.get_by_role("button", name="Clear filters").click()
        expect(page.get_by_test_id("ip-prefix-table")).to_contain_text("10.0.0.0/8")
