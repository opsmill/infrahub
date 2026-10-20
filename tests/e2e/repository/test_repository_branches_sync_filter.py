"""Filtering the Branches section of a repository by sync status."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from helpers import Deadline, generate_random_branch_name
from infrahub_sdk.task.models import TaskFilter, TaskState
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

pytestmark = pytest.mark.shard_branches_repo

REPOSITORY_NAME = "demo-edge"
ERROR_IMPORT = "error-import"
IN_SYNC = "in-sync"
GIT_BRANCH_CREATE_WORKFLOW = "git-repositories-create-branch"


@dataclass(frozen=True)
class SyncStatusBranches:
    shared_prefix: str
    failed_import: str
    in_sync: str


async def create_git_branch_with_sync_status(
    branch_api: BranchAPI, client: InfrahubClient, name: str, sync_status: str
) -> None:
    # A read-write repository lists only the branches synchronized with Git.
    await branch_api.create(name, sync_with_git=True)

    # The Git branch creation writes the repository on the branch, so the status is set once it completes.
    created_in_git = TaskFilter(workflow=[GIT_BRANCH_CREATE_WORKFLOW], branch=name, state=[TaskState.COMPLETED])
    deadline = Deadline(f"branch {name} to be created in Git")
    while not await client.task.count(filters=created_in_git):
        await deadline.tick(pause=2.0)

    repository = await client.get(kind="CoreRepository", name__value=REPOSITORY_NAME, branch=name)
    repository.sync_status.value = sync_status
    await repository.save()


class TestRepositoryBranchesSyncStatusFilter:
    @pytest.fixture
    async def branches(
        self, branch_api: BranchAPI, infrahub_client: InfrahubClient, demo_edge_repo: None
    ) -> AsyncGenerator[SyncStatusBranches, None]:
        shared_prefix = generate_random_branch_name("repo-sync-filter")
        failed_import = f"{shared_prefix}-failed"
        in_sync = f"{shared_prefix}-ok"
        created: list[str] = []
        try:
            created.append(failed_import)
            await create_git_branch_with_sync_status(branch_api, infrahub_client, failed_import, ERROR_IMPORT)
            created.append(in_sync)
            await create_git_branch_with_sync_status(branch_api, infrahub_client, in_sync, IN_SYNC)
            yield SyncStatusBranches(shared_prefix=shared_prefix, failed_import=failed_import, in_sync=in_sync)
        finally:
            for name in created:
                with contextlib.suppress(Exception):
                    await branch_api.delete(name)

    async def test_lists_only_the_branches_with_the_selected_sync_status(
        self, admin_page: Page, infrahub_client: InfrahubClient, branches: SyncStatusBranches
    ) -> None:
        repository = await infrahub_client.get(kind="CoreRepository", name__value=REPOSITORY_NAME)
        await admin_page.goto(f"/objects/CoreRepository/{repository.id}")

        branches_section = admin_page.get_by_role("region", name="Branches", exact=True)
        # The section pages by ten rows, so the search keeps both branches on the first page before filtering.
        await branches_section.get_by_role("searchbox", name="Search branches").fill(branches.shared_prefix)
        await expect(branches_section.get_by_role("link", name=branches.failed_import, exact=True)).to_be_visible()
        await expect(branches_section.get_by_role("link", name=branches.in_sync, exact=True)).to_be_visible()

        await branches_section.get_by_role("button", name=re.compile(r"^Filter")).click()
        await admin_page.get_by_role("option", name="Sync Status", exact=True).click()
        await admin_page.get_by_role("option", name=re.compile(r"^Import Error")).click()
        await admin_page.get_by_role("button", name="Apply", exact=True).click()

        await expect(admin_page.get_by_role("row", name="Sync Status contains Import Error")).to_be_visible()
        await expect(branches_section.get_by_role("link", name=branches.failed_import, exact=True)).to_be_visible()
        await expect(branches_section.get_by_role("link", name=branches.in_sync, exact=True)).to_be_hidden()
