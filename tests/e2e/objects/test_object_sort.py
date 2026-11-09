"""Port of frontend/app/tests/e2e/objects/object-sort.spec.ts.

Sort picker on /objects/InfraDevice: the schema default order, switching to a
custom direction, stacking sorts through the grouped and searchable pickers,
removing them again, editing a row's field, and resetting to the schema
default. Sorting is URL state only (no mutations), so the test runs as Admin
against main; data_sites provides the demo devices whose names and sites drive
the expected row order (name ascending starts at atl1-core1, descending at
ord1-leaf2).
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


class TestObjectSort:
    async def test_customize_sort_combine_multiple_sorts_and_reset_to_default(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        sort_button = admin_page.get_by_role("button", name=re.compile(r"^Sort( \d+)?$"))
        sort_rows = admin_page.get_by_role("grid", name="Sort keys").get_by_role("row")
        first_row_link = admin_page.get_by_test_id("data-table-row").first.get_by_role("link").first

        # navigate and verify the schema default order
        await admin_page.goto("/objects/InfraDevice")
        await expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()
        await expect(first_row_link).to_have_text("atl1-core1")

        # open the sort editor showing the schema default
        await sort_button.click()
        await expect(admin_page.get_by_text("Default order · applied now")).to_be_visible()
        await expect(admin_page.get_by_role("button", name=re.compile(r"Sort field"))).to_contain_text("Name")
        await expect(admin_page.get_by_role("button", name=re.compile(r"Sort direction"))).to_contain_text("Ascending")
        await expect(admin_page.get_by_role("button", name="Why this sort can't be removed")).to_be_visible()

        # switch the direction to descending
        await admin_page.get_by_role("button", name=re.compile(r"Sort direction")).click()
        await admin_page.get_by_role("option", name="Descending").click()

        await expect(admin_page.get_by_text("Custom order")).to_be_visible()
        await expect(admin_page).to_have_url(re.compile(r"sort=name__value__desc"))
        await expect(sort_button).to_contain_text("1")
        await expect(first_row_link).to_have_text("ord1-leaf2")

        # add a secondary sort on a relationship field
        await admin_page.get_by_role("button", name="Add sort").click()

        await admin_page.get_by_placeholder("Search...").fill("nonexistent field")
        await expect(admin_page.get_by_text("No fields match")).to_be_visible()
        await admin_page.get_by_placeholder("Search...").fill("")

        await admin_page.get_by_role("menuitem", name="Site").click()
        await admin_page.get_by_role("menuitem", name="Name", exact=True).click()
        await admin_page.get_by_role("menuitem", name="Ascending").click()

        await expect(sort_rows).to_have_count(2)
        await expect(sort_button).to_contain_text("2")
        await expect(admin_page).to_have_url(re.compile(r"sort=name__value__desc(,|%2C)site__name__value__asc"))
        # The primary sort is unchanged, so the first row stays the same.
        await expect(first_row_link).to_have_text("ord1-leaf2")

        # add a metadata sort from the search results
        await admin_page.get_by_role("button", name="Add sort").click()
        await admin_page.get_by_placeholder("Search...").fill("updated")
        await admin_page.get_by_role("menuitem", name="Updated at").click()
        await admin_page.get_by_role("menuitem", name="Descending").click()

        await expect(sort_rows).to_have_count(3)
        await expect(sort_button).to_contain_text("3")
        await expect(admin_page).to_have_url(
            re.compile(r"sort=name__value__desc(,|%2C)site__name__value__asc(,|%2C)node_metadata__updated_at__desc")
        )

        # remove the primary and metadata sorts
        await sort_rows.first.get_by_role("button", name="Remove sort").click()

        await expect(sort_rows).to_have_count(2)
        await expect(admin_page).not_to_have_url(re.compile(r"name__value__desc"))
        await expect(first_row_link).to_have_text(re.compile(r"^atl1-"))

        await sort_rows.last.get_by_role("button", name="Remove sort").click()

        await expect(sort_rows).to_have_count(1)
        await expect(sort_button).to_contain_text("1")
        await expect(admin_page).to_have_url(re.compile(r"sort=site__name__value__asc"))
        await expect(admin_page).not_to_have_url(re.compile(r"node_metadata__updated_at"))

        # change the sort field from the row select
        await admin_page.get_by_role("button", name=re.compile(r"Sort field")).click()
        await admin_page.get_by_placeholder("Search...").fill("name")
        await admin_page.get_by_role("option", name="Name", exact=True).click()

        await expect(admin_page).to_have_url(re.compile(r"sort=name__value__asc"))
        await expect(first_row_link).to_have_text("atl1-core1")

        # reset to the default order
        # Both the header button and the row button are named "Reset to default";
        # the header one comes first in DOM order.
        await admin_page.get_by_role("button", name="Reset to default").first.click()

        await expect(admin_page.get_by_text("Default order · applied now")).to_be_visible()
        await expect(admin_page).not_to_have_url(re.compile(r"sort="))
        await expect(sort_button).not_to_contain_text("1")
        await expect(first_row_link).to_have_text("atl1-core1")
