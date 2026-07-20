"""/proposed-changes list ordering.

The proposed-changes list (both the Opened and Closed tabs) must be ordered by
creation date, newest first. Regression guard for the list previously coming
back in an arbitrary (node-uuid) order, which buried recently created proposed
changes.

The test owns all of its data: it creates three throwaway branches and one
proposed change per branch through the SDK, so it needs neither the demo
dataset nor the demo-edge repository.

Note on the Closed tab: ordering is by *creation* time, not by when each
proposed change was closed. The test closes the proposed changes in reverse
creation order to prove the list still comes back newest-created-first (the
most recently closed one is not floated to the top).
"""

from __future__ import annotations

import contextlib
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
    """Return the proposed-change ids in the order they are rendered in the list."""
    listbox = page.get_by_role("listbox")
    hrefs = await listbox.locator('a[href*="/proposed-changes/"]').evaluate_all(
        "els => els.map((e) => e.getAttribute('href'))"
    )
    order: list[str] = []
    for href in hrefs:
        pc_id = href.split("/proposed-changes/", 1)[1].split("?", 1)[0].split("/", 1)[0]
        if pc_id and pc_id not in order:
            order.append(pc_id)
    return order


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
