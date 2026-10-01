"""Repositories and Git state columns on the branches list."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from helpers import BranchAPI
    from playwright.async_api import Locator, Page

# The table is a flat CSS grid with no row element, so a row's cells are the siblings that follow
# its identifier cell, in column order.
REPOSITORIES_OFFSET = 3
GIT_STATE_OFFSET = 4


def _identifier_cell(page: Page, branch: str) -> Locator:
    return page.get_by_test_id("branch-identifier-cell").filter(
        has=page.get_by_role("checkbox", name=f"Select {branch}", exact=True)
    )


def _row_cell(identifier_cell: Locator, offset: int) -> Locator:
    return identifier_cell.locator(f"xpath=following-sibling::*[{offset}]")


class TestBranchesGitColumns:
    @pytest.fixture
    async def branch_without_git_sync(self, branch_api: BranchAPI) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("branches-no-git-")
        await branch_api.create(name, sync_with_git=False)
        yield name
        try:
            await branch_api.delete(name)
        except Exception:
            logger.warning("Teardown could not delete branch %s", name, exc_info=True)

    async def test_broken_repository_leads_its_branch_row(
        self, admin_page: Page, broken_repository: Callable[..., Awaitable[tuple[str, str, str]]]
    ) -> None:
        branch, repository_name, _ = await broken_repository(sync_with_git=True)

        await admin_page.goto("/branches")

        identifier_cell = _identifier_cell(admin_page, branch)
        await expect(identifier_cell).to_have_count(1)

        repository_link = _row_cell(identifier_cell, REPOSITORIES_OFFSET).get_by_role(
            "link", name=repository_name, exact=True
        )
        await expect(repository_link).to_be_visible()
        await expect(repository_link).to_have_attribute("href", re.compile(rf"branch={re.escape(branch)}"))

        await expect(
            _row_cell(identifier_cell, GIT_STATE_OFFSET).get_by_text("Import Error", exact=True)
        ).to_be_visible()

    async def test_branch_without_git_sync_reads_not_synced(
        self, admin_page: Page, branch_without_git_sync: str
    ) -> None:
        await admin_page.goto("/branches")

        identifier_cell = _identifier_cell(admin_page, branch_without_git_sync)
        await expect(identifier_cell).to_have_count(1)
        await expect(_row_cell(identifier_cell, REPOSITORIES_OFFSET)).to_have_text("Not synced with Git")
