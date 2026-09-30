"""Repository, Git state and Commit columns on the branches list."""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from helpers import BranchAPI
    from playwright.async_api import Locator, Page

# The table is a flat CSS grid with no row element, so a row's cells are the siblings that follow
# its identifier cell, in column order.
REPOSITORY_OFFSET = 3
GIT_STATE_OFFSET = 4
COMMIT_OFFSET = 5


def _identifier_cell(page: Page, branch: str, repository_name: str | None = None) -> Locator:
    xpath = f"//*[@data-testid='branch-identifier-cell'][.//a[normalize-space()='{branch}']]"
    if repository_name is not None:
        xpath += f"[following-sibling::*[{REPOSITORY_OFFSET}][.//a[normalize-space()='{repository_name}']]]"
    return page.get_by_test_id("branches-table").locator(f"xpath={xpath}")


def _row_cell(identifier_cell: Locator, offset: int) -> Locator:
    return identifier_cell.locator(f"xpath=following-sibling::*[{offset}]")


class TestBranchesGitColumns:
    @pytest.fixture
    async def branch_without_git_sync(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("branches-no-git-")
        await branch_api.create(name, sync_with_git=False)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_broken_repository_row_shows_its_git_state_and_commit(
        self, admin_page: Page, broken_repository: Callable[..., Awaitable[tuple[str, str, str]]]
    ) -> None:
        branch, repository_name, _ = await broken_repository(sync_with_git=True)

        await admin_page.goto("/branches")

        identifier_cell = _identifier_cell(admin_page, branch, repository_name)
        await expect(identifier_cell).to_have_count(1)

        await expect(
            _row_cell(identifier_cell, REPOSITORY_OFFSET).get_by_role("link", name=repository_name, exact=True)
        ).to_be_visible()
        await expect(_row_cell(identifier_cell, GIT_STATE_OFFSET)).to_have_text("Import Error")

        commit_cell = _row_cell(identifier_cell, COMMIT_OFFSET)
        await expect(commit_cell.get_by_text(re.compile(r"^[0-9a-f]{7}$"))).to_be_visible()
        await expect(commit_cell.get_by_role("button", name=re.compile(r"^Copy commit [0-9a-f]{40}$"))).to_be_visible()

    async def test_branch_without_git_sync_reads_not_synced(
        self, admin_page: Page, branch_without_git_sync: str
    ) -> None:
        await admin_page.goto("/branches")

        identifier_cell = _identifier_cell(admin_page, branch_without_git_sync)
        await expect(identifier_cell).to_have_count(1)
        await expect(_row_cell(identifier_cell, REPOSITORY_OFFSET)).to_have_text("Not synced with Git")
