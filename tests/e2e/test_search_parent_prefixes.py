"""Port of frontend/app/tests/e2e/search-parent-prefixes.spec.ts.

Search-anywhere "Parent Prefixes" section: containing prefixes for an IP,
absent for non-IP queries, empty state for an unmatched IP, and navigation to a
prefix detail page. Depends on data_sites' IP data (10.0.0.0/8, 10.0.0.0/16,
and 10.0.0.2 — the second loopback).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestSearchParentPrefixes:
    async def test_display_parent_prefixes_for_ip_address(self, admin_page: Page, data_sites: SitesHandle) -> None:
        await admin_page.goto("/")
        await admin_page.get_by_test_id("search-anywhere-trigger").click()
        await expect(admin_page.get_by_test_id("search-anywhere")).to_be_visible()

        await admin_page.get_by_test_id("search-anywhere-input").fill("10.0.0.2")
        search_dialog = admin_page.get_by_test_id("search-anywhere")
        await expect(search_dialog.get_by_text("Parent Prefixes")).to_be_visible()
        await expect(
            search_dialog.get_by_role("option", name=re.compile(r"10\.0\.0\.0\/16.*IP Prefix"))
        ).to_be_visible()
        await expect(search_dialog.get_by_role("option", name=re.compile(r"10\.0\.0\.0\/8.*IP Prefix"))).to_be_visible()

        # the existing IP address appears in the Objects section
        await expect(search_dialog.get_by_text("Objects")).to_be_visible()

    async def test_no_parent_prefixes_for_non_ip_search(self, admin_page: Page, data_sites: SitesHandle) -> None:
        await admin_page.goto("/")
        await admin_page.get_by_test_id("search-anywhere-trigger").click()
        await admin_page.get_by_test_id("search-anywhere-input").fill("atl1")

        search_dialog = admin_page.get_by_test_id("search-anywhere")
        await expect(search_dialog.get_by_text("Objects")).to_be_visible()
        await expect(search_dialog.get_by_text("Parent Prefixes")).not_to_be_visible()

    async def test_empty_parent_prefixes_state_for_unmatched_ip(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        await admin_page.goto("/")
        await admin_page.get_by_test_id("search-anywhere-trigger").click()
        await admin_page.get_by_test_id("search-anywhere-input").fill("203.0.113.5")

        search_dialog = admin_page.get_by_test_id("search-anywhere")
        await expect(search_dialog.get_by_text("Parent Prefixes")).to_be_visible()
        await expect(search_dialog.get_by_text("No containing prefixes found")).to_be_visible()

    async def test_navigate_to_prefix_detail_from_parent_prefix(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        await admin_page.goto("/")
        await admin_page.get_by_test_id("search-anywhere-trigger").click()
        await admin_page.get_by_test_id("search-anywhere-input").fill("10.0.0.2")

        search_dialog = admin_page.get_by_test_id("search-anywhere")
        await expect(search_dialog.get_by_text("Parent Prefixes")).to_be_visible()
        await search_dialog.get_by_role("option", name=re.compile(r"10\.0\.0\.0\/16.*IP Prefix")).click()

        await expect(admin_page.get_by_role("heading", name="10.0.0.0/16")).to_be_visible()
        assert "/ipam" in admin_page.url
