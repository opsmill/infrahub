"""/proposed-changes list ordering and the Sort picker.

The proposed-changes list (both the Opened and Closed tabs) defaults to creation
date, newest first. Regression guard for the list previously coming back in an
arbitrary (node-uuid) order, which buried recently created proposed changes.

The toolbar carries the generic Sort picker: choosing a field (e.g. the
"Created at" / "Updated at" node metadata) and a direction persists the order in
the `sort` query param. The default order is the absence of a param — the
CoreProposedChange schema defines no order_by, so clearing the custom sort
drops the param and the list falls back to newest created first.

The filter bar's field chips open the object table's column-header menu, so a
chip offers both sorting and filtering for its field from one popover.

The tests own all of their data: three throwaway branches and one proposed
change per branch through the SDK, so they need neither the demo dataset nor the
demo-edge repository.

Note on the default order: it is by *creation* time, never by when a proposed
change was closed. The tests close proposed changes in reverse creation order,
which keeps the default order stable while making the update order the exact
reverse — so an assertion on one cannot pass under the other.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode
    from playwright.async_api import Page


async def _rendered_pc_order(page: Page) -> list[str]:
    """Return the proposed-change ids in the order they are rendered in the list.

    Changing the order restarts the query, which empties the list until the first
    page of the new order arrives — so wait for a row before reading, otherwise
    the scrape races the refetch and comes back empty.
    """
    listbox = page.get_by_role("listbox")
    rows = listbox.locator('a[href*="/proposed-changes/"]')
    await expect(rows.first).to_be_visible()
    hrefs = await rows.evaluate_all("els => els.map((e) => e.getAttribute('href'))")
    order: list[str] = []
    for href in hrefs:
        pc_id = href.split("/proposed-changes/", 1)[1].split("?", 1)[0].split("/", 1)[0]
        if pc_id and pc_id not in order:
            order.append(pc_id)
    return order


async def _open_sort_picker(page: Page) -> None:
    """Open the Sort picker popover (the trigger carries a count badge once a sort is applied)."""
    await page.get_by_role("button", name=re.compile(r"^Sort( \d+)?$")).click()


async def _add_sort(page: Page, field: str, direction: str) -> None:
    """Pick a sort from scratch: choose a field, then its direction in the submenu.

    Ends with Escape so the popover doesn't cover the first rows of the list.
    """
    await _open_sort_picker(page)
    await page.get_by_role("menuitem", name=field).click()
    await page.get_by_role("menuitem", name=direction).click()
    await page.keyboard.press("Escape")


class TestProposedChangesOrdering:
    @pytest.fixture
    async def proposed_changes(
        self,
        infrahub_client: InfrahubClient,
        schema_base: None,
    ) -> AsyncGenerator[list[InfrahubNode], None]:
        """Create three proposed changes, oldest first, each on its own branch."""
        created: list[tuple[InfrahubNode, str]] = []
        try:
            for index in range(3):
                branch_name = generate_random_branch_name(f"pc-order-{index}")
                await infrahub_client.branch.create(branch_name=branch_name, sync_with_git=False)
                pc = await infrahub_client.create(
                    kind="CoreProposedChange",
                    name=generate_random_branch_name(f"pc-order-e2e-{index}"),
                    source_branch=branch_name,
                    destination_branch="main",
                )
                await pc.save()
                created.append((pc, branch_name))
            yield [pc for pc, _ in created]
        finally:
            for pc, branch_name in created:
                with contextlib.suppress(Exception):
                    await pc.delete()
                with contextlib.suppress(Exception):
                    await infrahub_client.branch.delete(branch_name=branch_name)

    async def test_list_is_ordered_newest_first(self, admin_page: Page, proposed_changes: list[InfrahubNode]) -> None:
        oldest, middle, newest = proposed_changes
        expected = [newest.id, middle.id, oldest.id]

        # Opened tab (default): newest created proposed change on top.
        await admin_page.goto("/proposed-changes")
        await expect(admin_page.locator(f'a[href*="/proposed-changes/{newest.id}"]')).to_be_visible()
        opened_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in opened_order if pc_id in expected] == expected

        # Close them in reverse creation order to prove ordering ignores close time.
        for pc in (newest, middle, oldest):
            pc.state.value = "closed"
            await pc.save()

        # Closed tab: still ordered by creation date, newest first.
        await admin_page.goto("/proposed-changes?pr_state=closed")
        await expect(admin_page.locator(f'a[href*="/proposed-changes/{newest.id}"]')).to_be_visible()
        closed_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in closed_order if pc_id in expected] == expected

    async def test_sort_picker_flips_the_creation_order(
        self, admin_page: Page, proposed_changes: list[InfrahubNode]
    ) -> None:
        oldest, middle, newest = proposed_changes
        newest_first = [newest.id, middle.id, oldest.id]

        await admin_page.goto("/proposed-changes")
        await expect(admin_page.locator(f'a[href*="/proposed-changes/{newest.id}"]')).to_be_visible()

        await _add_sort(admin_page, "Created at", "Ascending")

        await expect(admin_page).to_have_url(re.compile(r"sort=node_metadata__created_at__asc"))
        oldest_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in oldest_order if pc_id in newest_first] == list(reversed(newest_first))

        # The default order is the absence of a param, so clearing the sort drops it entirely.
        await _open_sort_picker(admin_page)
        await admin_page.get_by_role("button", name="Clear sort").click()
        await admin_page.keyboard.press("Escape")

        await expect(admin_page).not_to_have_url(re.compile(r"sort="))
        restored_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in restored_order if pc_id in newest_first] == newest_first

    async def test_sort_picker_orders_by_update_date(
        self, admin_page: Page, proposed_changes: list[InfrahubNode]
    ) -> None:
        oldest, middle, newest = proposed_changes
        newest_first = [newest.id, middle.id, oldest.id]

        # Closing in reverse creation order makes the update order the exact reverse of the
        # creation order, so neither assertion below can pass under the other ordering.
        for pc in (newest, middle, oldest):
            pc.state.value = "closed"
            await pc.save()

        await admin_page.goto("/proposed-changes?pr_state=closed")
        await expect(admin_page.locator(f'a[href*="/proposed-changes/{newest.id}"]')).to_be_visible()

        listbox = admin_page.get_by_role("listbox")
        await expect(listbox.get_by_text("Updated")).to_have_count(0)

        await _add_sort(admin_page, "Updated at", "Descending")

        await expect(listbox.get_by_text("Updated").first).to_be_visible()

        await expect(admin_page).to_have_url(re.compile(r"sort=node_metadata__updated_at__desc"))
        updated_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in updated_order if pc_id in newest_first] == list(reversed(newest_first))

        # Flip the direction from the applied-sort row inside the picker.
        await _open_sort_picker(admin_page)
        await admin_page.get_by_role("button", name=re.compile(r"Sort direction")).click()
        await admin_page.get_by_role("option", name="Ascending").click()
        await admin_page.keyboard.press("Escape")

        await expect(admin_page).to_have_url(re.compile(r"sort=node_metadata__updated_at__asc"))
        least_updated_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in least_updated_order if pc_id in newest_first] == newest_first

    async def test_field_chip_sorts_and_filters(self, admin_page: Page, proposed_changes: list[InfrahubNode]) -> None:
        oldest, middle, newest = proposed_changes
        newest_first = [newest.id, middle.id, oldest.id]

        await admin_page.goto("/proposed-changes")
        await expect(admin_page.locator(f'a[href*="/proposed-changes/{newest.id}"]')).to_be_visible()

        # Branch names embed their creation index, so their ascending order is the creation order.
        await admin_page.get_by_role("button", name="Source Branch").click()
        await admin_page.get_by_role("menuitem", name="Sort ascending").click()

        await expect(admin_page).to_have_url(re.compile(r"sort=source_branch__value__asc"))
        branch_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in branch_order if pc_id in newest_first] == list(reversed(newest_first))

        # The same chip also filters its field.
        await admin_page.get_by_role("button", name="Source Branch").click()
        await admin_page.get_by_role("menuitem", name="Filter").click()
        filter_form = admin_page.get_by_test_id("attribute-filter-form")
        await filter_form.get_by_role("textbox").fill(str(newest.source_branch.value))
        await filter_form.get_by_role("button", name="Apply").click()

        await expect(admin_page.locator(f'a[href*="/proposed-changes/{oldest.id}"]')).not_to_be_visible()
        await expect(admin_page.locator(f'a[href*="/proposed-changes/{newest.id}"]')).to_be_visible()
