"""Port of frontend/app/tests/e2e/branches/merge-branch.spec.ts.

Branch - Merge action: the merge button is disabled during the merge and stays
disabled once the merge completes. The branch is created/deleted via the API
(branch_api), so the test owns all of its data and needs no demo dataset.
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

    from helpers import BranchAPI
    from playwright.async_api import Page


class TestBranchMergeAction:
    @pytest.fixture
    async def branch_name(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("merge-branch")
        await branch_api.create(name)
        yield name
        # afterAll: the test merges the branch; deletion may already be moot.
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_disable_merge_button_during_merge_and_reenable_when_complete(
        self, admin_page: Page, branch_name: str
    ) -> None:
        # access the branch details page
        await admin_page.goto(f"/branches/{branch_name}")
        await admin_page.get_by_text("Tasks").click()
        await expect(admin_page.get_by_text("Loading...Loading...")).to_be_visible()
        await expect(admin_page.get_by_text("Loading...Loading...")).not_to_be_visible()
        await expect(admin_page.get_by_text("No task")).to_be_visible()

        # Merge the branch and verify button state
        await admin_page.get_by_role("button", name="Merge", exact=True).click()
        await expect(admin_page.get_by_text("Branch merge requested!")).to_be_visible()
        await expect(admin_page.get_by_role("button", name="Merge", exact=True)).to_be_disabled()
        await expect(admin_page.get_by_text("COMPLETEDMerge branch graphQL")).to_be_visible(timeout=5 * 60 * 1000)
        await expect(admin_page.get_by_role("button", name="Merge", exact=True)).to_be_disabled()
