from __future__ import annotations

from typing import TYPE_CHECKING

from git import Repo

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.git.repository import get_initialized_repo
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreRepository
    from infrahub.database import InfrahubDatabase

GIT_BRANCH = "production"
REPOSITORY_NAME = "repository-with-non-main-default-branch"
READ_ONLY_REPOSITORY_NAME = "read-only-repository-with-non-main-ref"


def create_upstream_repository(directory: Path, branch: str) -> None:
    directory.mkdir()
    upstream = Repo.init(directory, initial_branch=branch)
    (directory / "file.txt").write_text("content")
    upstream.index.add(["file.txt"])
    upstream.index.commit("First commit")


class TestRepositoryDefaultBranch(TestInfrahubApp):
    async def test_on_demand_clone_checks_out_configured_default_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A worker with no local copy of a repository clones it on the repository default branch."""
        assert registry.default_branch != GIT_BRANCH

        source_dir = tmp_path / "upstream"
        create_upstream_repository(directory=source_dir, branch=GIT_BRANCH)

        node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await node.new(
            db=db,
            name=REPOSITORY_NAME,
            location=str(source_dir),
            default_branch=GIT_BRANCH,
        )
        await node.save(db=db)
        operational_status_before = node.operational_status.value

        repo = await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name=REPOSITORY_NAME,
            repository_kind=InfrahubKind.REPOSITORY,
        )

        assert repo.get_git_repo_main().active_branch.name == GIT_BRANCH

        reloaded: CoreRepository = await NodeManager.get_one(
            db=db, id=node.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert reloaded.operational_status.value == operational_status_before

    async def test_on_demand_clone_checks_out_configured_ref(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A worker with no local copy of a read-only repository clones it on the ref it tracks."""
        assert registry.default_branch != GIT_BRANCH

        source_dir = tmp_path / "upstream"
        create_upstream_repository(directory=source_dir, branch=GIT_BRANCH)

        node = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
        await node.new(
            db=db,
            name=READ_ONLY_REPOSITORY_NAME,
            location=str(source_dir),
            ref=GIT_BRANCH,
        )
        await node.save(db=db)

        repo = await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name=READ_ONLY_REPOSITORY_NAME,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
        )

        assert repo.get_git_repo_main().active_branch.name == GIT_BRANCH
