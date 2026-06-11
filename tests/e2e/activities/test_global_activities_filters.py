"""Port of frontend/app/tests/e2e/activities/global-activities-filters.spec.ts.

Global activity log filters: by branch, event type, has-children, primary/related
node and account. The source is a serial (test.slow) describe, but it relies only
on execution order, not on objects created by earlier tests, so each test is made
self-contained and depends on (admin_page, data_scenario_branches): the branch
filter targets the platform-conflict scenario branch and the accounts come
transitively via rbac.

The "Filter by account" test expects "Jack Bauer logged in via password", an event
that only exists once jbauer has logged in. It therefore also depends on the
`read_only_storage_state` fixture, which performs that jbauer UI login.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from helpers import Deadline
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from data.handles import ScenarioBranchesHandle
    from playwright.async_api import Locator, Page


async def _filter_until_indexed(
    page: Page, waiting_for: str, apply_filter: Callable[[], Awaitable[None]], expected_row: Callable[[], Locator]
) -> None:
    """Apply an activity-log filter, retrying until the expected entry is indexed.

    Activity entries are written asynchronously by the task-workers, and the
    entries these filters target come from the LAST mutations of the data load
    (the scenario branches, the role logins), so right after provisioning the
    workers may still be draining the event backlog. Retry the whole
    navigate+filter+assert flow under a Deadline, like the suite's other
    reload-until-visible activity waits.
    """
    deadline = Deadline(waiting_for)
    while True:
        await page.goto("/activities")
        await apply_filter()
        try:
            await expect(expected_row()).to_be_visible(timeout=10_000)
        except AssertionError:
            await deadline.tick()
            continue
        return


class TestGlobalActivitiesFilters:
    async def test_filter_by_branch(self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle) -> None:
        async def apply_branch_filter() -> None:
            await admin_page.get_by_role("button", name="Branch").click()
            await admin_page.get_by_role("option", name="platform-conflict").click()
            await admin_page.get_by_role("button", name="Apply").click()

        await _filter_until_indexed(
            admin_page,
            waiting_for="the platform-conflict branch activities to be indexed",
            apply_filter=apply_branch_filter,
            expected_row=lambda: admin_page.get_by_text("platform-conflict").nth(1),
        )
        await admin_page.get_by_role("button", name="Branch platform-conflict").click()
        await expect(admin_page.get_by_text("main").nth(1)).to_be_visible()

    async def test_filter_by_event_type(self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle) -> None:
        await admin_page.goto("/activities")
        await admin_page.get_by_role("button", name="Event Type").click()
        await admin_page.get_by_role("option", name="Node created").click()
        await admin_page.get_by_role("button", name="Apply").click()
        await expect(admin_page.get_by_text("created").nth(1)).to_be_visible()
        await admin_page.get_by_role("button", name="Event Type").click()
        await expect(admin_page.get_by_text("Node created")).to_be_hidden()
        await admin_page.get_by_role("button", name="Event Type").click()
        await admin_page.get_by_role("option", name="Node deleted").click()
        await admin_page.get_by_role("button", name="Apply").click()
        await expect(admin_page.get_by_text("deleted").nth(1)).to_be_visible()

    async def test_filter_by_children(self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle) -> None:
        await admin_page.goto("/activities")
        await admin_page.get_by_role("button", name="Has Children").click()
        await admin_page.get_by_text("True").click()
        await admin_page.get_by_role("button", name="Apply").click()
        await expect(admin_page.get_by_test_id("activity-has-children-icon").first).to_be_visible()

    async def test_filter_by_nodes(self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle) -> None:
        await admin_page.goto("/activities")
        await admin_page.get_by_role("button", name="Primary Node").click()
        await admin_page.get_by_role("option", name="Account", exact=True).click()
        await admin_page.get_by_role("option", name="Chloe O'Brian").click()
        await admin_page.get_by_role("button", name="Apply").click()
        await expect(admin_page.get_by_text("Chloe O'Brian").nth(1)).to_be_visible()
        await admin_page.get_by_role("button", name="Primary Node Chloe O'Brian").click()
        await admin_page.get_by_role("button", name="Related Node").click()
        await admin_page.get_by_role("option", name="Account", exact=True).click()
        await admin_page.get_by_role("option", name="CRM Synchronization").click()
        await admin_page.get_by_role("button", name="Apply").click()
        await expect(admin_page.get_by_text("CRM Synchronization").nth(1)).to_be_visible()

    async def test_filter_by_account(
        self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle, read_only_storage_state: str
    ) -> None:
        async def apply_account_filter() -> None:
            await admin_page.get_by_role("button", name="Account").click()
            await admin_page.get_by_role("option", name="Jack Bauer").click()
            await admin_page.get_by_role("button", name="Apply").click()

        await _filter_until_indexed(
            admin_page,
            waiting_for="the jbauer login activity to be indexed",
            apply_filter=apply_account_filter,
            expected_row=lambda: admin_page.get_by_text("logged in via password").first,
        )
