"""Port of frontend/app/tests/e2e/objects/object-header-sort.spec.ts.

Sorting from the column-header menu on /objects/InfraDevice: sort descending
from the Name header (URL state, indicator, persistence across reload),
toggle-clear back to the schema default, replacing a toolbar-built multi-field
sort with a single-field header sort, and sorting by a related attribute
through the Site header's "Sort by" submenu — with the pointer and with the
keyboard alone. Sorting is URL state only (no mutations), so the tests run as
Admin against main; data_sites provides the demo devices (name ascending
starts at atl1-core1, descending at ord1-leaf2; within a site the order is an
implicit uuid tiebreaker, so site-sorted assertions only pin the site prefix).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from data.handles import SitesHandle
    from playwright.async_api import Page


class TestObjectHeaderSort:
    async def test_sort_from_header_persist_on_reload_and_toggle_clear(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        first_row_link = admin_page.get_by_test_id("data-table-row").first.get_by_role("link").first
        name_header = admin_page.get_by_test_id("object-items").get_by_role("button", name="Name")

        # navigate and verify the schema default order
        await admin_page.goto("/objects/InfraDevice")
        await expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()
        await expect(first_row_link).to_have_text("atl1-core1")

        # sort descending from the Name header
        await name_header.click()
        await admin_page.get_by_role("menuitem", name="Sort descending").click()

        await expect(admin_page).to_have_url(re.compile(r"sort=name__value__desc"))
        await expect(first_row_link).to_have_text("ord1-leaf2")
        await expect(admin_page.get_by_role("button", name="Name sorted descending")).to_be_visible()

        # reload and verify the sort persists
        await admin_page.reload()
        await expect(admin_page).to_have_url(re.compile(r"sort=name__value__desc"))
        await expect(first_row_link).to_have_text("ord1-leaf2")
        await expect(admin_page.get_by_role("button", name="Name sorted descending")).to_be_visible()

        # toggle-clear restores the default order
        await name_header.click()
        await admin_page.get_by_role("menuitem", name="Sort descending").click()

        await expect(admin_page).not_to_have_url(re.compile(r"sort="))
        await expect(first_row_link).to_have_text("atl1-core1")
        await expect(admin_page.get_by_role("button", name="Name sorted descending")).not_to_be_visible()

    async def test_header_sort_replaces_toolbar_built_multi_field_sort(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        sort_button = admin_page.get_by_role("button", name=re.compile(r"^Sort( \d+)?$"))
        sort_rows = admin_page.get_by_role("grid", name="Sort keys").get_by_role("row")
        name_header = admin_page.get_by_test_id("object-items").get_by_role("button", name="Name")

        # navigate to the device list
        await admin_page.goto("/objects/InfraDevice")
        await expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()

        # build a two-field sort in the toolbar sort editor
        await sort_button.click()
        await admin_page.get_by_role("button", name=re.compile(r"Sort direction")).click()
        await admin_page.get_by_role("option", name="Descending").click()

        await admin_page.get_by_role("button", name="Add sort").click()
        await admin_page.get_by_role("menuitem", name="Site").click()
        await admin_page.get_by_role("menuitem", name="Name", exact=True).click()
        await admin_page.get_by_role("menuitem", name="Ascending").click()

        await expect(sort_rows).to_have_count(2)
        await expect(admin_page).to_have_url(re.compile(r"sort=name__value__desc(,|%2C)site__name__value__asc"))
        # The rerender after adding the sort drops focus to the body, where
        # Escape never reaches the editor popover — refocus inside it first.
        await admin_page.get_by_role("button", name="Add sort").focus()
        await admin_page.keyboard.press("Escape")
        await expect(admin_page.get_by_role("grid", name="Sort keys")).not_to_be_visible()

        # sort ascending from the Name header
        await name_header.click()
        await admin_page.get_by_role("menuitem", name="Sort ascending").click()

        await expect(admin_page).to_have_url(re.compile(r"sort=name__value__asc"))
        await expect(admin_page).not_to_have_url(re.compile(r"site__name__value__asc"))
        await expect(admin_page.get_by_role("button", name="Name sorted ascending")).to_be_visible()

        # verify the toolbar sort editor shows exactly the header sort
        await sort_button.click()
        await expect(sort_rows).to_have_count(1)
        await expect(admin_page.get_by_role("button", name=re.compile(r"Sort field"))).to_contain_text("Name")
        await expect(admin_page.get_by_role("button", name=re.compile(r"Sort direction"))).to_contain_text("Ascending")

    async def test_sort_by_related_attribute_from_site_header(self, admin_page: Page, data_sites: SitesHandle) -> None:
        first_row_link = admin_page.get_by_test_id("data-table-row").first.get_by_role("link").first
        site_header = admin_page.get_by_test_id("object-items").get_by_role("button", name="Site")

        # navigate and verify the schema default order
        await admin_page.goto("/objects/InfraDevice")
        await expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()
        await expect(first_row_link).to_have_text("atl1-core1")

        # sort ascending by the site name through the Sort by submenu
        await site_header.click()
        await admin_page.get_by_role("menuitem", name="Sort by").click()
        await admin_page.get_by_role("menuitem", name="Name", exact=True).click()
        await admin_page.get_by_role("menuitem", name="Ascending").click()

        await expect(admin_page).to_have_url(re.compile(r"sort=site__name__value__asc"))
        await expect(first_row_link).to_have_text(re.compile(r"^atl1-"))
        await expect(admin_page.get_by_role("button", name="Site sorted ascending")).to_be_visible()

    async def test_sort_by_related_attribute_using_only_the_keyboard(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        first_row_link = admin_page.get_by_test_id("data-table-row").first.get_by_role("link").first
        site_header = admin_page.get_by_test_id("object-items").get_by_role("button", name="Site")

        # navigate and verify the schema default order
        await admin_page.goto("/objects/InfraDevice")
        await expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()
        await expect(first_row_link).to_have_text("atl1-core1")

        # walk the menu and submenus with the keyboard
        await site_header.focus()
        await admin_page.keyboard.press("Enter")
        await expect(admin_page.get_by_role("menuitem", name="Sort by")).to_be_focused()

        await admin_page.keyboard.press("ArrowRight")
        await expect(admin_page.get_by_role("menuitem", name="City")).to_be_focused()

        await admin_page.keyboard.press("ArrowDown")
        await expect(admin_page.get_by_role("menuitem", name="Name", exact=True)).to_be_focused()

        await admin_page.keyboard.press("ArrowRight")
        await expect(admin_page.get_by_role("menuitem", name="Ascending")).to_be_focused()

        await admin_page.keyboard.press("Enter")
        await expect(admin_page).to_have_url(re.compile(r"sort=site__name__value__asc"))
        await expect(first_row_link).to_have_text(re.compile(r"^atl1-"))
        await expect(admin_page.get_by_role("button", name="Site sorted ascending")).to_be_visible()
