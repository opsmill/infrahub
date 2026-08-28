"""Column show/hide on /objects/InfraDevice (INFP-119).

Covers the one thing the component tests cannot: that a pasted link carrying
`?hide_columns=` round-trips through the real router and the real schema, and
that the toolbar Columns picker puts the column back — clearing the param
rather than pinning the table to today's default.

Column visibility is URL state only (no mutations), so — like
`test_object_header_sort.py` — the test runs as Admin against main with no
throwaway branch. `data_sites` provides the demo devices (the schema default
order starts at atl1-core1).

`exact=True` is load-bearing on every "Description" locator: InfraDevice also
carries a `computed_description` attribute, whose "Computed Description" label
substring-matches Playwright's default name matching.
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


class TestObjectColumns:
    async def test_shared_hide_link_round_trips_and_the_picker_restores_the_column(
        self, admin_page: Page, data_sites: SitesHandle
    ) -> None:
        table = admin_page.get_by_test_id("object-items")
        rows = admin_page.get_by_test_id("data-table-row")
        first_row_link = rows.first.get_by_role("link").first
        description_header = table.get_by_role("button", name="Description", exact=True)
        name_header = table.get_by_role("button", name="Name", exact=True)
        columns_button = admin_page.get_by_role("button", name=re.compile(r"^Columns"))
        description_item = admin_page.get_by_role("menu", name="Toggle columns").get_by_role(
            "menuitem", name="Description", exact=True
        )

        # open a shared link that hides one column
        await admin_page.goto("/objects/InfraDevice?hide_columns=description")
        await expect(admin_page.get_by_role("heading", name="Device")).to_be_visible()

        # the table rendered real rows -- a hidden column must not cost the data
        await expect(first_row_link).to_have_text("atl1-core1")
        await expect(rows).not_to_have_count(0)

        # only the named column went
        await expect(description_header).not_to_be_visible()
        await expect(name_header).to_be_visible()

        # the toolbar advertises the one departure from the default column set
        await expect(columns_button.get_by_text("1", exact=True)).to_be_visible()

        # re-check the column in the picker
        await columns_button.click()
        await description_item.click()

        # back to the default: no param left behind, column on screen again
        await expect(admin_page).not_to_have_url(re.compile(r"hide_columns"))
        await expect(description_header).to_be_visible()
        await expect(first_row_link).to_have_text("atl1-core1")
