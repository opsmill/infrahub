"""/proposed-changes list ordering and the Sort menu.

The proposed-changes list (both the Opened and Closed tabs) defaults to creation
date, newest first. Regression guard for the list previously coming back in an
arbitrary (node-uuid) order, which buried recently created proposed changes.

The Sort menu then offers four date orders — Newest, Oldest, Recently updated,
Least recently updated — persisted in the `sort` query param. The default order
carries no param, so choosing Newest clears it.

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


async def _pick_sort(page: Page, option: str | re.Pattern[str]) -> None:
    """Open the Sort menu and choose one of its date orders."""
    await page.get_by_role("button", name="Sort").click()
    await page.get_by_role("menuitem", name=option).click()


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

    async def test_sort_menu_flips_the_creation_order(
        self, admin_page: Page, proposed_changes: list[InfrahubNode]
    ) -> None:
        oldest, middle, newest = proposed_changes
        newest_first = [newest.id, middle.id, oldest.id]

        await admin_page.goto("/proposed-changes")
        await expect(admin_page.locator(f'a[href*="/proposed-changes/{newest.id}"]')).to_be_visible()

        await _pick_sort(admin_page, "Oldest")

        await expect(admin_page).to_have_url(re.compile(r"sort=node_metadata__created_at__asc"))
        oldest_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in oldest_order if pc_id in newest_first] == list(reversed(newest_first))

        # The default order is the absence of a param, so choosing it drops the param entirely.
        await _pick_sort(admin_page, "Newest")

        await expect(admin_page).not_to_have_url(re.compile(r"sort="))
        restored_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in restored_order if pc_id in newest_first] == newest_first

    async def test_sort_menu_orders_by_update_date(
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

        # The default order says nothing about update dates, so rows don't carry one.
        await expect(admin_page.get_by_role("listbox")).not_to_contain_text("updated")

        await _pick_sort(admin_page, re.compile(r"^Recently updated"))

        await expect(admin_page).to_have_url(re.compile(r"sort=node_metadata__updated_at__desc"))
        updated_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in updated_order if pc_id in newest_first] == list(reversed(newest_first))

        # Rows now explain their own position by showing the date they are ordered by.
        await expect(admin_page.get_by_role("listbox")).to_contain_text("updated")

        await _pick_sort(admin_page, "Least recently updated")

        await expect(admin_page).to_have_url(re.compile(r"sort=node_metadata__updated_at__asc"))
        least_updated_order = await _rendered_pc_order(admin_page)
        assert [pc_id for pc_id in least_updated_order if pc_id in newest_first] == newest_first
