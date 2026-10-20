"""Filtering the Branches section of a repository by sync status.

A read-write repository lists only the branches synchronized with Git, so the throwaway branch is
created with Git synchronization on and marked as failed to import once Infrahub has created it in Git.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name
from infrahub_sdk.task.models import TaskFilter, TaskState
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

pytestmark = pytest.mark.shard_branches_repo

REPOSITORY_NAME = "demo-edge"
ERROR_IMPORT = "error-import"
GIT_BRANCH_CREATE_WORKFLOW = "git-repositories-create-branch"


class TestRepositoryBranchesSyncStatusFilter:
    @pytest.fixture(scope="class")
    async def branch_with_failed_import(
        self, infrahub_client: InfrahubClient, demo_edge_repo: None
    ) -> AsyncGenerator[str, None]:
        """A Git-synchronized branch where the demo-edge repository is marked as failed to import."""
        name = generate_random_branch_name("repo-sync-filter")
        await infrahub_client.branch.create(branch_name=name, sync_with_git=True)

        # The Git branch creation writes the repository on the branch, so the status is set once it completes.
        created_in_git = TaskFilter(workflow=[GIT_BRANCH_CREATE_WORKFLOW], branch=name, state=[TaskState.COMPLETED])
        deadline = Deadline(f"branch {name} to be created in Git")
        while not await infrahub_client.task.count(filters=created_in_git):
            await deadline.tick(pause=2.0)

        repository = await infrahub_client.get(kind="CoreRepository", name__value=REPOSITORY_NAME, branch=name)
        repository.sync_status.value = ERROR_IMPORT
        await repository.save()

        yield name

        with contextlib.suppress(Exception):
            await infrahub_client.branch.delete(branch_name=name)

    async def test_lists_only_the_branches_with_the_selected_sync_status(
        self, admin_page: Page, infrahub_client: InfrahubClient, branch_with_failed_import: str
    ) -> None:
        repository = await infrahub_client.get(kind="CoreRepository", name__value=REPOSITORY_NAME)
        await admin_page.goto(f"/objects/CoreRepository/{repository.id}")

        branches = admin_page.get_by_role("region", name="Branches", exact=True)
        await expect(branches.get_by_role("link", name="main", exact=True)).to_be_visible()

        await branches.get_by_role("button", name=re.compile(r"^Filter")).click()
        await admin_page.get_by_role("option", name="Sync Status", exact=True).click()
        await admin_page.get_by_role("option", name=re.compile(r"^Import Error")).click()
        await admin_page.get_by_role("button", name="Apply", exact=True).click()

        await expect(admin_page.get_by_role("row", name="Sync Status contains Import Error")).to_be_visible()
        await expect(branches.get_by_role("link", name=branch_with_failed_import, exact=True)).to_be_visible()
        await expect(branches.get_by_role("link", name="main", exact=True)).to_be_hidden()
