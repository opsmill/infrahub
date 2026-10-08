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
    from collections.abc import AsyncGenerator

    from broken_repository import BrokenRepository
    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page


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

    async def test_branch_row_shows_broken_repository_and_import_error(
        self, admin_page: Page, broken_repository: BrokenRepository
    ) -> None:
        await admin_page.goto("/branches")
        await admin_page.get_by_role("searchbox", name="Search").fill(broken_repository.branch)

        repositories_cell = admin_page.get_by_test_id(f"branch-repositories-cell-{broken_repository.branch}")
        repository_link = repositories_cell.get_by_role("link", name=broken_repository.repository_name, exact=True)
        await expect(repository_link).to_be_visible()
        await expect(repository_link).to_have_attribute(
            "href", re.compile(rf"branch={re.escape(broken_repository.branch)}")
        )

        git_state_cell = admin_page.get_by_test_id(f"branch-git-state-cell-{broken_repository.branch}")
        await expect(git_state_cell.get_by_text("Import Error", exact=True)).to_be_visible()

    async def test_branch_without_git_sync_lists_only_read_only_repositories(
        self, admin_page: Page, infrahub_client: InfrahubClient, branch_without_git_sync: str
    ) -> None:
        read_only_names = [
            repository.name.value for repository in await infrahub_client.all(kind="CoreReadOnlyRepository")
        ]

        await admin_page.goto("/branches")
        await admin_page.get_by_role("searchbox", name="Search").fill(branch_without_git_sync)

        repositories_cell = admin_page.get_by_test_id(f"branch-repositories-cell-{branch_without_git_sync}")
        if not read_only_names:
            await expect(repositories_cell).to_have_text("Not synced with Git")
            return

        # Other tests can leave read-only repositories, and a branch without Git sync still lists them.
        names_pattern = "|".join(re.escape(name) for name in read_only_names)
        await expect(repositories_cell.get_by_role("link").first).to_have_text(re.compile(rf"^(?:{names_pattern})$"))
