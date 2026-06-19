"""Port of frontend/app/tests/e2e/ipam/ipam-tree.spec.ts.

The IPAM tree: lazy expand of children, navigate to a prefix summary, search,
expand-to-selection on reload, and collapse/expand the whole tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestIpamTree:
    async def test_load_child_tree_item_on_expand(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")
        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")

        # all top level prefixes are collapsed
        await expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_hidden()

        # view direct children of a top level prefix
        await ipam_tree.get_by_role("button", name="Expand 10.0.0.0/8").click()
        await expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.1.0.12/31")).to_be_hidden()

        # view children of a children prefix
        await ipam_tree.get_by_role("button", name="Expand 10.1.0.0/16").click()
        await expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.1.0.12/31")).to_be_visible()

        # on first load, the tree expands to the selected prefix position
        await ipam_tree.get_by_text("10.1.0.12/31").click()
        await expect(page.get_by_role("heading", name="10.1.0.12/31")).to_be_visible()
        await page.reload()
        await expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.1.0.0/16")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.1.0.12/31")).to_be_visible()
        await expect(ipam_tree.get_by_role("row", name="10.1.0.12/31")).to_contain_class("bg-neutral-100")

    async def test_go_to_prefix_summary_on_click(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")
        await page.get_by_label("IPAM tree").get_by_text("10.0.0.0/8").click()
        await expect(page.get_by_role("heading", name="10.0.0.0/8")).to_be_visible()

    async def test_search_an_ip_prefix(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")
        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")

        # search on IPAM tree
        await expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()
        await page.get_by_role("searchbox", name="IPAM Tree search").fill("10.2")
        await expect(ipam_tree.get_by_text("10.2.0.0/16")).to_be_visible()
        assert await ipam_tree.get_by_role("row").count() == 1

        # search results are visible after navigation
        await ipam_tree.get_by_text("10.2.0.0/16").click()
        await expect(page.get_by_role("heading", name="10.2.0.0/16")).to_be_visible()
        await expect(ipam_tree.get_by_text("10.2.0.0/16")).to_be_visible()
        assert await ipam_tree.get_by_role("row").count() == 1

        # reset IPAM search
        await page.get_by_role("searchbox", name="IPAM Tree search").fill("")
        await expect(ipam_tree.get_by_text("10.0.0.0/8")).to_be_visible()

    async def test_collapse_ipam_tree(self, page: Page, data_sites: SitesHandle) -> None:
        await page.goto("/ipam")
        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")

        await expect(ipam_tree).to_be_visible()
        await page.get_by_role("button", name="toggle IPAM tree").click()
        await expect(ipam_tree).to_be_hidden()
        await page.get_by_role("button", name="toggle IPAM tree").click()
        await expect(ipam_tree).to_be_visible()
