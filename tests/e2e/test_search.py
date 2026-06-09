"""Port of frontend/app/tests/e2e/search.spec.ts.

Search-anywhere modal: open/close (click, Esc, Ctrl/Cmd+K), the Device menu
link, the no-results message, node + IPAM results, and lookup by UUID. Runs
anonymously; the result tests rely on the demo data / menu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestSearchAnywhere:
    def test_open_search_anywhere_modal(self, page: Page) -> None:
        page.goto("/")

        # open with click
        page.get_by_test_id("search-anywhere-trigger").click()
        expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        # close with Esc
        page.locator("body").press("Escape")
        expect(page.get_by_test_id("search-anywhere")).not_to_be_visible()

        # open with the keyboard shortcut
        page.keyboard.press("ControlOrMeta+k")
        expect(page.get_by_test_id("search-anywhere")).to_be_visible()

    def test_displays_link_to_device_list(self, page: Page, infrastructure_menu: None) -> None:
        page.goto("/")
        page.get_by_test_id("search-anywhere-trigger").click()
        expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        page.get_by_test_id("search-anywhere-input").fill("devi")
        expect(page.get_by_test_id("search-anywhere")).to_contain_text("Go to")
        page.get_by_role("option", name="Menu Device").click()
        expect(page.get_by_role("heading", name="Device")).to_be_visible()
        assert "/objects/InfraDevice" in page.url

    def test_message_when_no_results_found(self, page: Page) -> None:
        page.goto("/")
        page.get_by_test_id("search-anywhere-trigger").click()
        expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        page.get_by_test_id("search-anywhere-input").fill("no_results_query_for_test")
        expect(
            page.get_by_test_id("search-anywhere").get_by_role(
                "option", name="Search in docs: no_results_query_for_test"
            )
        ).to_be_visible()

    def test_display_results_on_search_nodes(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/")
        page.get_by_test_id("search-anywhere-trigger").click()
        expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        # a matching node result
        page.get_by_test_id("search-anywhere-input").fill("atl1")
        expect(page.get_by_test_id("search-anywhere").get_by_role("option", name="atl1 Location Site")).to_be_visible()

        # a matching IPAM result
        page.get_by_test_id("search-anywhere-input").fill("10.0")
        expect(page.get_by_role("option", name="10.0.0.0/8 Ipam IP Prefix IP")).to_be_visible()
        expect(page.get_by_role("option", name="10.0.0.0/16 Ipam IP Prefix IP")).to_be_visible()
        expect(page.get_by_text("IP Namespacedefault").first).to_be_visible()
        expect(page.get_by_text("IP NamespacedefaultAddress10.0.0.2/32Description-")).to_be_visible()

    def test_display_result_when_searching_by_uuid(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/objects/InfraAutonomousSystem")

        page.get_by_role("link", name="AS174 174").click()
        uuid = page.locator("dd").first.text_content()
        assert uuid

        page.get_by_test_id("search-anywhere-trigger").click()
        expect(page.get_by_test_id("search-anywhere")).to_be_visible()

        page.get_by_test_id("search-anywhere-input").fill(uuid)
        expect(page.get_by_role("option", name="AS174 174 Infra Autonomous System")).to_be_visible()
