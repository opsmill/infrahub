"""Port of frontend/app/tests/e2e/ipam/ipam-tree.spec.ts.

The IPAM tree: lazy expand of children, navigate to a prefix summary, search,
expand-to-selection on reload, and collapse/expand the whole tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestIpamTree:
    def test_load_child_tree_item_on_expand(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/ipam")
        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")

        # all top level prefixes are collapsed
        expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_hidden()

        # view direct children of a top level prefix
        ipam_tree.get_by_role("button", name="Expand 10.0.0.0/8").click()
        expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_visible()
        expect(ipam_tree.get_by_text("10.1.0.12/31")).to_be_hidden()

        # view children of a children prefix
        ipam_tree.get_by_role("button", name="Expand 10.1.0.0/16").click()
        expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_visible()
        expect(ipam_tree.get_by_text("10.1.0.12/31")).to_be_visible()

        # on first load, the tree expands to the selected prefix position
        ipam_tree.get_by_text("10.1.0.12/31").click()
        expect(page.get_by_role("heading", name="10.1.0.12/31")).to_be_visible()
        page.reload()
        expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_visible()
        expect(ipam_tree.get_by_text("10.1.0.12/31")).to_be_visible()
        expect(ipam_tree.get_by_role("row", name="10.1.0.12/31")).to_contain_class("bg-neutral-100")

    def test_go_to_prefix_summary_on_click(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/ipam")
        page.get_by_label("IPAM tree").get_by_text("10.0.0.0/8").click()
        expect(page.get_by_role("heading", name="10.0.0.0/8")).to_be_visible()

    def test_search_an_ip_prefix(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/ipam")
        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")

        # search on IPAM tree
        expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        page.get_by_role("searchbox", name="IPAM Tree search").fill("10.2")
        expect(ipam_tree.get_by_text("10.2.0.0/16")).to_be_visible()
        assert ipam_tree.get_by_role("row").count() == 1

        # search results are visible after navigation
        ipam_tree.get_by_text("10.2.0.0/16").click()
        expect(page.get_by_role("heading", name="10.2.0.0/16")).to_be_visible()
        expect(ipam_tree.get_by_text("10.2.0.0/16")).to_be_visible()
        assert ipam_tree.get_by_role("row").count() == 1

        # reset IPAM search
        page.get_by_role("searchbox", name="IPAM Tree search").fill("")
        expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()

    def test_collapse_ipam_tree(self, page: Page, infrastructure_data: None) -> None:
        page.goto("/ipam")
        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")

        expect(ipam_tree).to_be_visible()
        page.get_by_role("button", name="toggle IPAM tree").click()
        expect(ipam_tree).to_be_hidden()
        page.get_by_role("button", name="toggle IPAM tree").click()
        expect(ipam_tree).to_be_visible()
