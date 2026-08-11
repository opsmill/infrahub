from __future__ import annotations

from typing import TYPE_CHECKING

from git.repo import Repo

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.file_repo import FileRepo

NEW_BRANCH = "branch-from-git"


class TestSyncBranchFlag(TestInfrahubApp):
    async def test_branch_imported_from_git_syncs_with_git(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        git_repo_car_dealership: FileRepo,
        git_repos_dir: Path,
    ) -> None:
        """A branch discovered on the remote must be created with sync_with_git enabled.

        Merging the branch, running its repository checks and generating its artifacts are all gated
        on that flag, so a branch imported without it silently skips the git side of a merge.
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

        # The branch is created after the clone so the sync treats it as a new remote branch.
        Repo(git_repo_car_dealership.path).git.branch(NEW_BRANCH, "main")

        collected = await repo.collect_pending_imports()
        assert [pending.infrahub_branch_name for pending in collected.imports] == [NEW_BRANCH]

        branch = await client.branch.get(branch_name=NEW_BRANCH)
        assert branch.sync_with_git is True
