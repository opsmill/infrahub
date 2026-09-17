from __future__ import annotations

from typing import TYPE_CHECKING

from git import Repo

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.git.repository import InfrahubRepository, _get_initialized_repo, get_initialized_repo
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
DECOY_FILE = "only-on-the-platform-default-branch.txt"
PROPOSED_CHANGE_BRANCH = "proposed-change-branch"


def create_upstream_repository(directory: Path, branch: str) -> None:
    directory.mkdir()
    upstream = Repo.init(directory, initial_branch=branch)
    (directory / "file.txt").write_text("content")
    upstream.index.add(["file.txt"])
    upstream.index.commit("First commit")


def add_decoy_platform_default_branch(directory: Path) -> None:
    """Give the remote a branch named after the platform default, holding a file the trunk lacks.

    Its presence is what turns a wrong-branch operation from an error into a silently wrong result,
    which is the shape of the defect on a worker whose clone is already warm.
    """
    upstream = Repo(directory)
    trunk = upstream.active_branch.name
    upstream.git.checkout("-b", registry.default_branch)
    (directory / DECOY_FILE).write_text("decoy")
    upstream.index.add([DECOY_FILE])
    upstream.index.commit("Commit only on the platform default branch")
    upstream.git.checkout(trunk)


def advance_trunk(directory: Path, content: str) -> None:
    upstream = Repo(directory)
    (directory / "file.txt").write_text(content)
    upstream.index.add(["file.txt"])
    upstream.index.commit("Advance the trunk")


class TestRepositoryDefaultBranch(TestInfrahubApp):
    async def test_warm_clone_operation_targets_configured_default_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A second construction on a worker that already has a clone still targets the trunk.

        The remote carries both the configured trunk and a branch named after the platform default,
        so an operation that resolves the wrong one succeeds while reading the wrong tree.
        """
        assert registry.default_branch != GIT_BRANCH

        source_dir = tmp_path / "upstream"
        create_upstream_repository(directory=source_dir, branch=GIT_BRANCH)
        add_decoy_platform_default_branch(directory=source_dir)

        node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await node.new(db=db, name=REPOSITORY_NAME, location=str(source_dir), default_branch=GIT_BRANCH)
        await node.save(db=db)

        await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name=REPOSITORY_NAME,
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=registry.default_branch,
        )

        advance_trunk(directory=source_dir, content="trunk content")

        # The factory caches the object for 30s; a real worker builds a fresh one once that lapses.
        _get_initialized_repo.cache_clear()
        warm_repo = await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name=REPOSITORY_NAME,
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=registry.default_branch,
        )

        await warm_repo.pull(branch_name=registry.default_branch, update_commit_value=False)

        worktree = warm_repo.directory_default
        assert (worktree / "file.txt").read_text() == "trunk content"
        assert not (worktree / DECOY_FILE).exists()

    async def test_proposed_change_merge_conflict_check_compares_against_the_configured_default_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A proposed change's merge-conflict check compares against the repository's own default branch.

        This is the matrix flow whose branch choice is least obvious: the object is constructed with
        the proposed change's source branch while the comparison target comes from the repository's
        default branch. Asserting on which files the check reported as conflicting is what catches the
        wrong target; a check that merely completed would pass either way.
        """
        assert registry.default_branch != GIT_BRANCH

        source_dir = tmp_path / "upstream"
        create_upstream_repository(directory=source_dir, branch=GIT_BRANCH)
        upstream = Repo(source_dir)

        # Both branches fork from the same commit and change the same file differently, so merging
        # one into the other conflicts. Forking the proposed change from the advanced trunk instead
        # would only fast-forward, and the check would report nothing whichever branch it compared.
        base_commit = upstream.head.commit.hexsha
        add_decoy_platform_default_branch(directory=source_dir)

        upstream.git.checkout(GIT_BRANCH)
        (source_dir / "file.txt").write_text("trunk side")
        upstream.index.add(["file.txt"])
        upstream.index.commit("Diverge the trunk")

        upstream.git.checkout("-b", PROPOSED_CHANGE_BRANCH, base_commit)
        (source_dir / "file.txt").write_text("proposed change side")
        upstream.index.add(["file.txt"])
        upstream.index.commit("Diverge the proposed change branch")
        upstream.git.checkout(GIT_BRANCH)

        node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await node.new(
            db=db, name="repository-for-merge-conflict-check", location=str(source_dir), default_branch=GIT_BRANCH
        )
        await node.save(db=db)

        await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name="repository-for-merge-conflict-check",
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=registry.default_branch,
        )

        # The check runs on a later flow, on a worker whose clone is already warm -- the state in
        # which the default branch used to be lost.
        _get_initialized_repo.cache_clear()
        repo = await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name="repository-for-merge-conflict-check",
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=registry.default_branch,
        )
        assert isinstance(repo, InfrahubRepository)
        await repo.create_branch_in_git(branch_name=PROPOSED_CHANGE_BRANCH, push_origin=False)

        # The destination is named as Infrahub sees it; the check has to map it onto the trunk. The
        # remote also carries a branch by that literal name, so a wrong mapping compares real content
        # rather than failing to resolve.
        conflicts = await repo.get_conflicts(source_branch=PROPOSED_CHANGE_BRANCH, dest_branch=registry.default_branch)

        assert conflicts == ["file.txt"]
        assert (repo.directory_default / "file.txt").read_text() == "trunk side"
        assert not (repo.directory_default / DECOY_FILE).exists()

    async def test_repository_existing_only_on_a_branch_resolves_its_configured_default_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A repository created inside an Infrahub branch resolves its own default branch there.

        The node is created in staging on a branch, and read on that branch; its default branch
        differs from Infrahub's, so a resolution that ignored either would pick the wrong tree.
        """
        assert registry.default_branch != GIT_BRANCH

        source_dir = tmp_path / "upstream"
        create_upstream_repository(directory=source_dir, branch=GIT_BRANCH)
        add_decoy_platform_default_branch(directory=source_dir)

        staging_branch = await create_branch(branch_name="staging-branch", db=db)

        node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=staging_branch)
        await node.new(
            db=db,
            name="repository-created-inside-a-branch",
            location=str(source_dir),
            default_branch=GIT_BRANCH,
            internal_status=RepositoryInternalStatus.STAGING.value,
        )
        await node.save(db=db)

        repo = await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name="repository-created-inside-a-branch",
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=staging_branch.name,
        )

        assert repo.get_git_repo_main().active_branch.name == GIT_BRANCH
        assert not (repo.directory_default / DECOY_FILE).exists()

        # The status is branch-local, so it is what proves the node was read on the branch the
        # operation runs on. The repository node itself is branch-agnostic and visible everywhere.
        assert isinstance(repo, InfrahubRepository)
        assert repo.internal_status is RepositoryInternalStatus.STAGING

        _get_initialized_repo.cache_clear()
        on_default_branch = await get_initialized_repo.fn(
            client=client,
            repository_id=node.id,
            name="repository-created-inside-a-branch",
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=registry.default_branch,
        )

        assert isinstance(on_default_branch, InfrahubRepository)
        assert on_default_branch.internal_status is not RepositoryInternalStatus.STAGING

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
            infrahub_branch_name=registry.default_branch,
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
            infrahub_branch_name=registry.default_branch,
        )

        assert repo.get_git_repo_main().active_branch.name == GIT_BRANCH
