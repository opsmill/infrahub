from __future__ import annotations

from typing import TYPE_CHECKING

from git.repo import Repo

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.file_repo import FileRepo

MERGED_BRANCH = "description-field"


class TestSyncMergedBranch(TestInfrahubApp):
    async def test_sync_skips_merged_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        git_repo_car_dealership: FileRepo,
        git_repos_dir: Path,
    ) -> None:
        """A merged (read-only) branch lingering on the remote must be skipped by the sync.

        Recording its commit issues CoreRepositoryUpdate, which is rejected for a merged branch. That
        rejection is not isolated per branch, so it aborts the whole sync instead of skipping the one
        branch.
        """
        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(
            db=db,
            name=git_repo_car_dealership.name,
            description="test repository",
            location=git_repo_car_dealership.path,
        )
        await obj.save(db=db)

        repo = await InfrahubRepository.new(
            id=obj.id,
            name=git_repo_car_dealership.name,
            location=git_repo_car_dealership.path,
            client=client,
        )

        # The branch has been merged: it is read-only but its branch object persists in the graph.
        branch = await create_branch(branch_name=MERGED_BRANCH, db=db)
        branch.status = BranchStatus.MERGED
        await branch.save(db=db)

        # The corresponding git branch is not deleted on merge, so it lingers on the remote and the
        # local clone does not have it, making the sync treat it as a new branch to record.
        Repo(git_repo_car_dealership.path).git.branch(MERGED_BRANCH, "main")

        collected = await repo.collect_pending_imports()

        assert MERGED_BRANCH not in [pending.infrahub_branch_name for pending in collected.imports]
