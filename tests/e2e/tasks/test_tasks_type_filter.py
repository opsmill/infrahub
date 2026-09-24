"""E2E coverage for the Type facet on the Tasks list.

With the facet unset the list is what it has always been. Selecting "System"
widens it to the internal background flows that carry no namespace tag.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from playwright.async_api import Page

TYPE_FIELD_LABEL = "Type"
SYSTEM_LABEL = "System"

# The filters query-string parameter carries JSON, so the field name arrives percent-encoded.
FILTER_IN_URL = re.compile(r"workflow_type__value")


async def _apply_type_filter(page: Page, option: str) -> None:
    await page.get_by_test_id("apply-filters").click()
    dialog = page.get_by_role("dialog")
    await expect(dialog.get_by_text(TYPE_FIELD_LABEL, exact=True)).to_be_visible()
    await dialog.get_by_role("combobox").nth(2).click()
    await page.get_by_role("option", name=option, exact=True).click()
    await dialog.get_by_role("button", name="Apply filters").click()


class TestTasksTypeFilter:
    async def test_selecting_system_reveals_internal_runs_and_narrows_the_count(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks")
        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()

        await _apply_type_filter(admin_page, SYSTEM_LABEL)

        await expect(admin_page.get_by_role("columnheader", name=TYPE_FIELD_LABEL)).to_be_visible()
        # Internal runs are the ones the default list structurally excluded.
        await expect(admin_page.get_by_role("cell", name=SYSTEM_LABEL).first).to_be_visible()

    async def test_the_type_filter_survives_a_reload_through_the_url(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks")
        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()

        await _apply_type_filter(admin_page, SYSTEM_LABEL)
        # The query-string write is deferred, so retry rather than reading the URL once.
        await expect(admin_page).to_have_url(FILTER_IN_URL)

        await admin_page.reload()

        await expect(admin_page).to_have_url(FILTER_IN_URL)
        await expect(admin_page.get_by_role("columnheader", name=TYPE_FIELD_LABEL)).to_be_visible()

    async def test_the_filter_count_reflects_the_type_selection_and_can_be_cleared(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks")
        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()
        await expect(admin_page.get_by_text("Filters: 0")).to_be_visible()

        await _apply_type_filter(admin_page, SYSTEM_LABEL)
        await expect(admin_page.get_by_text("Filters: 1")).to_be_visible()

        await admin_page.get_by_test_id("remove-filters").click()

        await expect(admin_page.get_by_text("Filters: 0")).to_be_visible()
        await expect(admin_page).not_to_have_url(FILTER_IN_URL)

    async def test_internal_runs_leave_the_branch_and_related_node_cells_empty(self, admin_page: Page) -> None:
        await admin_page.goto("/tasks")
        await expect(admin_page.get_by_role("heading", name="Task Overview")).to_be_visible()

        await _apply_type_filter(admin_page, SYSTEM_LABEL)

        internal_row = admin_page.get_by_role("row").filter(has=admin_page.get_by_role("cell", name=SYSTEM_LABEL))
        await expect(internal_row.first).to_be_visible()
        # Branch is the second column; an internal run carries no branch tag, so the cell renders
        # empty rather than erroring or showing a placeholder that implies a value.
        await expect(internal_row.first.locator("td").nth(1)).to_have_text("")
