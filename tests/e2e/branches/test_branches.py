"""Port of frontend/app/tests/e2e/branches/branches.spec.ts.

Branch creation and deletion through the UI. The legacy spec was a serial
`describe` that shared branch state across tests (one test created a branch a
later test deleted). pytest reorders tests by fixture usage, so that cross-test
ordering is not guaranteed; instead each test owns its branches here (created
via the API and cleaned up afterwards). Same coverage — UI create, branch
detail view, delete-non-selected, delete-selected, search — but order-robust.
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

    from data.handles import ScenarioBranchesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestBranchesCreationDeletion:
    @pytest.fixture
    async def new_branch_name(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        """A unique branch name to create via the UI; removed afterwards."""
        name = generate_random_branch_name("branches-create-")
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    @pytest.fixture
    async def existing_branch(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        """A branch created via the API for the test to view; removed afterwards."""
        name = generate_random_branch_name("branches-view-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_should_create_a_new_branch(self, admin_page: Page, new_branch_name: str) -> None:
        await admin_page.goto("/")
        await admin_page.get_by_test_id("branch-selector-trigger").click()
        await admin_page.get_by_test_id("create-branch-button").click()

        # Form
        await expect(admin_page.get_by_text("Create a new branch")).to_be_visible()
        await admin_page.get_by_label("New branch name *").fill(new_branch_name)
        await admin_page.get_by_text("New branch description").fill("branch creation test")
        await admin_page.get_by_role("button", name="Create a new branch").click()

        # After submit
        await expect(admin_page.get_by_role("button", name=new_branch_name, exact=True)).to_be_visible()
        await expect(admin_page).to_have_url(re.compile(rf".*?branch={new_branch_name}"))

    async def test_should_display_the_new_branch(self, admin_page: Page, existing_branch: str) -> None:
        await admin_page.goto("/")
        await admin_page.get_by_test_id("branch-selector-trigger").click()
        await expect(admin_page.get_by_label("branch list")).to_contain_text(existing_branch)

        await admin_page.get_by_role("link", name="View all branches").click()
        await expect(admin_page).to_have_url(re.compile(r".*/branches"))

        await admin_page.get_by_role("link", name=existing_branch).click()
        await expect(admin_page.get_by_text(f"Name{existing_branch}")).to_be_visible()

        await admin_page.get_by_role("button", name="View node metadata").click()
        await expect(admin_page.get_by_text("Created at")).to_be_visible()
        await expect(admin_page.get_by_text("Created by")).to_be_visible()
        await expect(admin_page.get_by_text("Updated at")).to_be_visible()
        await expect(admin_page.get_by_text("Updated by")).to_be_visible()

        assert f"/branches/{existing_branch}" in admin_page.url

    async def test_delete_non_selected_branch_and_remain_on_current(
        self, admin_page: Page, branch_api: BranchAPI
    ) -> None:
        active_branch = generate_random_branch_name("branches-active-")
        target_branch = generate_random_branch_name("branches-target-")
        await branch_api.create(active_branch)
        await branch_api.create(target_branch)
        try:
            # View the target branch while the active (current) branch is a different one.
            await admin_page.goto(f"/branches/{target_branch}?branch={active_branch}")

            await admin_page.get_by_role("button", name="Delete").click()

            modal_delete = admin_page.get_by_test_id("modal-delete")
            await expect(modal_delete.get_by_role("heading", name="Delete")).to_be_visible()
            await expect(
                modal_delete.get_by_text(f"Are you sure you want to remove the branch `{target_branch}`?")
            ).to_be_visible()
            await modal_delete.get_by_role("button", name="Delete").click()

            # we should stay on the active branch
            await expect(admin_page.get_by_role("heading", name="Branches")).to_be_visible()
            await expect(admin_page.get_by_test_id("branch-selector-trigger")).to_contain_text(active_branch)
            await admin_page.get_by_test_id("branch-selector-trigger").click()
            await expect(admin_page.get_by_label("branch list")).to_contain_text(active_branch)
            await expect(admin_page.get_by_label("branch list")).not_to_contain_text(target_branch)
            assert f"/branches?branch={active_branch}" in admin_page.url
        finally:
            for name in (active_branch, target_branch):
                with contextlib.suppress(Exception):
                    await branch_api.delete(name)

    async def test_delete_currently_selected_branch(self, admin_page: Page, branch_api: BranchAPI) -> None:
        branch = generate_random_branch_name("branches-selected-")
        await branch_api.create(branch)
        try:
            await admin_page.goto("/branches")
            await admin_page.get_by_text(branch).click()
            await admin_page.get_by_role("button", name="Delete").click()
            await admin_page.get_by_test_id("modal-delete-confirm").click()

            await expect(admin_page.get_by_role("heading", name="Branches")).to_be_visible()
            assert "/branches" in admin_page.url
            await admin_page.get_by_test_id("branch-selector-trigger").click()
            await expect(admin_page.get_by_label("branch list")).not_to_contain_text(branch)
        finally:
            with contextlib.suppress(Exception):
                await branch_api.delete(branch)

    async def test_search_for_a_branch(self, admin_page: Page, data_scenario_branches: ScenarioBranchesHandle) -> None:
        await admin_page.goto("/branches")
        await expect(admin_page.get_by_role("link", name="main", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("link", name="den1-maintenance-conflict")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="atl1-delete-upstream")).to_be_visible()
        await admin_page.get_by_role("searchbox", name="Search").fill("main")
        await expect(admin_page.get_by_role("link", name="main", exact=True)).to_be_visible()
        await expect(admin_page.get_by_role("link", name="den1-maintenance-conflict")).to_be_visible()
        await expect(admin_page.get_by_role("link", name="atl1-delete-upstream")).not_to_be_visible()

        await admin_page.get_by_role("searchbox", name="Search").fill("")
        await expect(admin_page.get_by_role("link", name="atl1-delete-upstream")).to_be_visible()
