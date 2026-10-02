from __future__ import annotations

import shutil
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from git import Repo

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
from infrahub.core.registry import registry
from infrahub.git.models import GitRepositoryWarmUp
from infrahub.git.repository import (
    _get_initialized_repo,  # noqa: PLC2701 the process-wide memo has no public reset
    get_initialized_repo,
)
from infrahub.git.state.warm_up import RepositoryWarmUp
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.operations.git import repository as repository_operations
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.message_bus import BusRecorder
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def _local_branch_commit(repos_dir: Path, repository: CoreRepository, branch_name: str) -> str:
    """Return the commit a local copy's branch points at, which is what the sync compares with the remote."""
    return Repo(repos_dir / repository.id / "main").heads[branch_name].commit.hexsha


def _clone_request(repository: CoreRepository, initiator: str) -> messages.RefreshGitClone:
    return messages.RefreshGitClone(
        meta=Meta(initiator_id=initiator),
        repository_id=repository.id,
        repository_name=repository.name.value,
        repository_kind=InfrahubKind.REPOSITORY,
        infrahub_branch_name=registry.default_branch,
    )


@contextmanager
def _without_local_copy(repos_dir: Path, repository_id: str) -> Iterator[None]:
    """Leave this worker without a local copy, as a worker scaled up after the repository was added."""
    shutil.rmtree(repos_dir / repository_id, ignore_errors=True)
    # The initialized repository is memoized per process, and would otherwise stand in for the deleted copy.
    _get_initialized_repo.cache_clear()
    try:
        yield
    finally:
        _get_initialized_repo.cache_clear()


@asynccontextmanager
async def _without_imported_commit(
    db: InfrahubDatabase, repository: CoreRepository | CoreReadOnlyRepository
) -> AsyncIterator[None]:
    imported = repository.commit.value
    repository.commit.value = None
    await repository.save(db=db)
    try:
        yield
    finally:
        repository.commit.value = imported
        await repository.save(db=db)


def _advance(upstream: Repo) -> None:
    """Move the remote past the imported commit."""
    Path(upstream.working_dir, "not-imported.txt").write_text("not imported", encoding="utf-8")
    upstream.index.add(["not-imported.txt"])
    upstream.index.commit("Advance the remote past the imported commit")


class TestRepositoryWarmUp(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        FileRepo(name="read-only-repo", sources_directory=git_repos_source_dir_module_scope)
        # The repository declares a check targeting this group, so the import fails without it.
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people")
        await people.save(db=db)

    @pytest.fixture(scope="class")
    async def repository(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
    ) -> CoreRepository:
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

        return await NodeManager.get_one(db=db, id=client_repository.id, kind=CoreRepository, raise_on_error=True)

    @pytest.fixture(scope="class")
    async def read_only_repository(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
    ) -> CoreReadOnlyRepository:
        client_repository = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            data={
                "name": "read-only-repo",
                "location": f"{git_repos_source_dir_module_scope}/read-only-repo",
                "ref": "main",
            },
        )
        await client_repository.save()

        return await NodeManager.get_one(
            db=db, id=client_repository.id, kind=CoreReadOnlyRepository, raise_on_error=True
        )

    @pytest.fixture
    def cold_worker(self, repository: CoreRepository, git_repos_dir_module_scope: Path) -> Iterator[None]:
        with _without_local_copy(repos_dir=git_repos_dir_module_scope, repository_id=repository.id):
            yield

    @pytest.fixture
    def cold_read_only_worker(
        self, read_only_repository: CoreReadOnlyRepository, git_repos_dir_module_scope: Path
    ) -> Iterator[None]:
        with _without_local_copy(repos_dir=git_repos_dir_module_scope, repository_id=read_only_repository.id):
            yield

    @pytest.fixture
    def advanced_upstream(self, repository: CoreRepository, git_repos_source_dir_module_scope: Path) -> Iterator[str]:
        """Move the remote past the imported commit, and return the imported commit."""
        upstream = Repo(git_repos_source_dir_module_scope / "car-dealership")
        imported = upstream.head.commit.hexsha
        assert repository.commit.value == imported
        _advance(upstream=upstream)
        yield imported
        upstream.git.reset("--hard", imported)

    @pytest.fixture
    async def nothing_imported(self, db: InfrahubDatabase, repository: CoreRepository) -> AsyncIterator[None]:
        async with _without_imported_commit(db=db, repository=repository):
            yield

    @pytest.fixture
    async def read_only_nothing_imported(
        self, db: InfrahubDatabase, read_only_repository: CoreReadOnlyRepository
    ) -> AsyncIterator[None]:
        async with _without_imported_commit(db=db, repository=read_only_repository):
            yield

    @pytest.fixture
    async def existing_copy(self, client: InfrahubClient, repository: CoreRepository) -> None:
        await get_initialized_repo(
            client=client,
            repository_id=repository.id,
            name=repository.name.value,
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=registry.default_branch,
        )
        # Otherwise the memo answers the next initialization and the copy on disk is never looked at.
        _get_initialized_repo.cache_clear()

    @pytest.fixture
    def bus(self) -> BusRecorder:
        return BusRecorder()

    @pytest.fixture
    def warm_up(self, client: InfrahubClient, bus: BusRecorder) -> RepositoryWarmUp:
        return RepositoryWarmUp(
            client=client,
            message_bus=bus,
            lock_registry=InfrahubLockRegistry(local_only=True),
            worker_identity=WORKER_IDENTITY,
        )

    def _model(
        self,
        repository: CoreRepository | CoreReadOnlyRepository,
        default_branch: Branch,
        repository_kind: str = InfrahubKind.REPOSITORY,
    ) -> GitRepositoryWarmUp:
        return GitRepositoryWarmUp(
            repository_id=repository.id,
            repository_name=repository.name.value,
            repository_kind=repository_kind,
            location=repository.location.value,
            infrahub_branch_name=default_branch.name,
        )

    async def test_warm_up_clones_and_broadcasts_the_commit_imported_now(
        self,
        default_branch: Branch,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        advanced_upstream: str,
        bus: BusRecorder,
        warm_up: RepositoryWarmUp,
    ) -> None:
        """Every copy, this one included, is reset to the commit the graph holds, not the remote head just cloned.

        A copy left at the remote head would leave this worker's sync nothing to import.
        """
        await warm_up.warm_up(model=self._model(repository=repository, default_branch=default_branch))

        assert (
            _local_branch_commit(
                repos_dir=git_repos_dir_module_scope, repository=repository, branch_name=default_branch.name
            )
            == advanced_upstream
        )
        assert bus.messages == [
            messages.RefreshGitFetch(
                meta=Meta(initiator_id=WORKER_IDENTITY),
                location=repository.location.value,
                repository_id=repository.id,
                repository_name=repository.name.value,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=default_branch.name,
                infrahub_branch_id=str(default_branch.uuid),
                commit=advanced_upstream,
            )
        ]

    async def test_warm_up_leaves_a_read_write_repository_with_nothing_imported_to_its_sync(
        self,
        default_branch: Branch,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        nothing_imported: None,
        bus: BusRecorder,
        warm_up: RepositoryWarmUp,
    ) -> None:
        """A copy created here would sit at the remote head and leave the sync nothing to import."""
        await warm_up.warm_up(model=self._model(repository=repository, default_branch=default_branch))

        assert not (git_repos_dir_module_scope / repository.id).exists()
        assert bus.messages == []

    async def test_warm_up_clones_a_read_only_repository_with_nothing_imported_and_broadcasts_a_clone(
        self,
        default_branch: Branch,
        read_only_repository: CoreReadOnlyRepository,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
        cold_read_only_worker: None,
        read_only_nothing_imported: None,
        bus: BusRecorder,
        warm_up: RepositoryWarmUp,
    ) -> None:
        """With no commit to pin other workers to, they are asked to clone without checking anything out."""
        await warm_up.warm_up(
            model=self._model(
                repository=read_only_repository,
                default_branch=default_branch,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
            )
        )

        upstream_head = Repo(git_repos_source_dir_module_scope / "read-only-repo").head.commit.hexsha
        local_copy = Repo(git_repos_dir_module_scope / read_only_repository.id / "main")
        assert local_copy.commit("origin/main").hexsha == upstream_head
        assert bus.messages == [
            messages.RefreshGitClone(
                meta=Meta(initiator_id=WORKER_IDENTITY),
                repository_id=read_only_repository.id,
                repository_name=read_only_repository.name.value,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                infrahub_branch_name=default_branch.name,
            )
        ]

    async def test_a_worker_receiving_the_clone_request_creates_its_copy(
        self, client: InfrahubClient, repository: CoreRepository, git_repos_dir_module_scope: Path, cold_worker: None
    ) -> None:
        await repository_operations.clone.fn(message=_clone_request(repository=repository, initiator="another-worker"))

        assert (
            _local_branch_commit(
                repos_dir=git_repos_dir_module_scope, repository=repository, branch_name=registry.default_branch
            )
            == repository.commit.value
        )

    async def test_the_clone_request_leaves_an_existing_copy_as_it_is(
        self,
        client: InfrahubClient,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        existing_copy: None,
    ) -> None:
        local_copy = Repo(git_repos_dir_module_scope / repository.id / "main")
        head_before = local_copy.head.commit.hexsha
        worktrees_before = local_copy.git.worktree("list", "--porcelain")

        await repository_operations.clone.fn(message=_clone_request(repository=repository, initiator="another-worker"))

        assert local_copy.head.commit.hexsha == head_before
        assert local_copy.git.worktree("list", "--porcelain") == worktrees_before

    async def test_the_worker_that_sent_the_clone_request_ignores_it(
        self, client: InfrahubClient, repository: CoreRepository, git_repos_dir_module_scope: Path, cold_worker: None
    ) -> None:
        await repository_operations.clone.fn(message=_clone_request(repository=repository, initiator=WORKER_IDENTITY))

        assert not (git_repos_dir_module_scope / repository.id).exists()
