from __future__ import annotations

import asyncio
import shutil
from contextlib import asynccontextmanager, contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from git import Repo
from git.exc import GitCommandError
from infrahub_sdk import Config, InfrahubClient
from structlog.testing import capture_logs

from infrahub import lock
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
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.operations.git import repository as repository_operations
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.message_bus import BusRecorder
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, MutableMapping

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


@contextmanager
def _unreachable(upstream: Path) -> Iterator[None]:
    """Move the remote away so every fetch from it fails, and put it back afterwards."""
    moved = upstream.with_name(f"{upstream.name}-unreachable")
    upstream.rename(moved)
    try:
        yield
    finally:
        moved.rename(upstream)


@asynccontextmanager
async def _with_imported_commit(
    db: InfrahubDatabase, repository: CoreRepository | CoreReadOnlyRepository, commit: str | None
) -> AsyncIterator[None]:
    imported = repository.commit.value
    repository.commit.value = commit
    await repository.save(db=db)
    try:
        yield
    finally:
        repository.commit.value = imported
        await repository.save(db=db)


class SignallingClient(InfrahubClient):
    """An SDK client that awaits a hook before its first GraphQL call, then sends every call as usual."""

    def __init__(self, config: Config, before_first_query: Callable[[], Awaitable[None]]) -> None:
        super().__init__(config=config)
        self._before_first_query: Callable[[], Awaitable[None]] | None = before_first_query

    async def execute_graphql(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if self._before_first_query is not None:
            hook, self._before_first_query = self._before_first_query, None
            await hook()
        return await super().execute_graphql(*args, **kwargs)


FETCH_FAILURE_EVENT = "Could not fetch the local copy"


def _fetch_failures(records: list[MutableMapping[str, Any]]) -> list[MutableMapping[str, Any]]:
    return [record for record in records if record["event"] == FETCH_FAILURE_EVENT]


def _fetch_failure(repository: CoreRepository) -> dict[str, Any]:
    """The warning a fetch from the unreachable remote logs, git exiting with its fatal status."""
    return {"event": FETCH_FAILURE_EVENT, "repository": repository.name.value, "status": 128, "log_level": "warning"}


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
        async with _with_imported_commit(db=db, repository=repository, commit=None):
            yield

    @pytest.fixture
    async def read_only_nothing_imported(
        self, db: InfrahubDatabase, read_only_repository: CoreReadOnlyRepository
    ) -> AsyncIterator[None]:
        async with _with_imported_commit(db=db, repository=read_only_repository, commit=None):
            yield

    @pytest.fixture
    async def read_only_imported_commit_not_on_remote(
        self, db: InfrahubDatabase, read_only_repository: CoreReadOnlyRepository
    ) -> AsyncIterator[None]:
        """Leave the graph pointing at a commit the remote no longer has, as after a history rewrite."""
        async with _with_imported_commit(db=db, repository=read_only_repository, commit="0" * 40):
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
    def fetched_existing_copy(
        self, repository: CoreRepository, git_repos_dir_module_scope: Path, existing_copy: None
    ) -> None:
        Repo(git_repos_dir_module_scope / repository.id / "main").remotes.origin.fetch()

    @pytest.fixture
    def copy_whose_last_fetch_failed(
        self,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
        existing_copy: None,
    ) -> None:
        with _unreachable(upstream=git_repos_source_dir_module_scope / "car-dealership"), suppress(GitCommandError):
            Repo(git_repos_dir_module_scope / repository.id / "main").remotes.origin.fetch()

    @pytest.fixture
    def unreachable_upstream(self, git_repos_source_dir_module_scope: Path) -> Iterator[None]:
        """Make every fetch from the remote fail, while a local copy made beforehand stays valid."""
        with _unreachable(upstream=git_repos_source_dir_module_scope / "car-dealership"):
            yield

    @pytest.fixture
    def bus(self) -> BusRecorder:
        return BusRecorder()

    @pytest.fixture
    def warm_up(self, client: InfrahubClient, bus: BusRecorder) -> RepositoryWarmUp:
        return RepositoryWarmUp(
            client=client,
            message_bus=bus,
            lock_registry=lock.registry,
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
            infrahub_branch_name=default_branch.name,
        )

    async def test_warm_up_clones_at_the_remote_head_and_broadcasts_a_clone(
        self,
        default_branch: Branch,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
        cold_worker: None,
        advanced_upstream: str,
        bus: BusRecorder,
        warm_up: RepositoryWarmUp,
    ) -> None:
        """No local branch is moved back to the imported commit, so the warm-up cannot roll back a sync."""
        await warm_up.warm_up(model=self._model(repository=repository, default_branch=default_branch))

        upstream_head = Repo(git_repos_source_dir_module_scope / "car-dealership").head.commit.hexsha
        assert upstream_head != advanced_upstream
        local_copy = Repo(git_repos_dir_module_scope / repository.id / "main")
        assert local_copy.commit(f"origin/{default_branch.name}").hexsha == upstream_head
        assert (
            _local_branch_commit(
                repos_dir=git_repos_dir_module_scope, repository=repository, branch_name=default_branch.name
            )
            == upstream_head
        )
        assert (Path(local_copy.git_dir) / "FETCH_HEAD").is_file()
        assert bus.messages == [
            messages.RefreshGitClone(
                meta=Meta(initiator_id=WORKER_IDENTITY),
                repository_id=repository.id,
                repository_name=repository.name.value,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=default_branch.name,
            )
        ]

    async def test_warm_up_of_a_read_only_repository_whose_imported_commit_left_the_remote(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        read_only_repository: CoreReadOnlyRepository,
        cold_read_only_worker: None,
        read_only_imported_commit_not_on_remote: None,
        bus: BusRecorder,
        warm_up: RepositoryWarmUp,
    ) -> None:
        """Nothing repairs a read-only repository's copies later, so the broadcast must still reach every worker."""
        status_before = (
            await NodeManager.get_one(
                db=db, id=read_only_repository.id, kind=CoreReadOnlyRepository, raise_on_error=True
            )
        ).operational_status.value

        await warm_up.warm_up(
            model=self._model(
                repository=read_only_repository,
                default_branch=default_branch,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
            )
        )

        assert bus.messages == [
            messages.RefreshGitClone(
                meta=Meta(initiator_id=WORKER_IDENTITY),
                repository_id=read_only_repository.id,
                repository_name=read_only_repository.name.value,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                infrahub_branch_name=default_branch.name,
            )
        ]
        reloaded = await NodeManager.get_one(
            db=db, id=read_only_repository.id, kind=CoreReadOnlyRepository, raise_on_error=True
        )
        assert reloaded.operational_status.value == status_before

    async def test_warm_up_shares_a_clone_another_handler_started_on_this_worker(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        bus: BusRecorder,
    ) -> None:
        """A clone already started here waits for the repository lock, so the warm-up must not hold it meanwhile."""
        warm_up_querying = asyncio.Event()
        handler_cloning = asyncio.Event()

        async def start_the_handler_clone() -> None:
            warm_up_querying.set()
            await handler_cloning.wait()

        async def mark_handler_cloning() -> None:
            handler_cloning.set()

        async def clone_as_a_message_handler() -> None:
            await warm_up_querying.wait()
            await get_initialized_repo(
                client=SignallingClient(config=client.config, before_first_query=mark_handler_cloning),
                repository_id=repository.id,
                name=repository.name.value,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=default_branch.name,
            )

        # Started before the warm-up, so the clone does not inherit a repository lock the warm-up holds.
        handler = asyncio.create_task(clone_as_a_message_handler())
        warm_up = RepositoryWarmUp(
            client=SignallingClient(config=client.config, before_first_query=start_the_handler_clone),
            message_bus=bus,
            lock_registry=lock.registry,
            worker_identity=WORKER_IDENTITY,
        )

        try:
            await asyncio.wait_for(
                warm_up.warm_up(model=self._model(repository=repository, default_branch=default_branch)), timeout=60
            )
        finally:
            await asyncio.wait_for(handler, timeout=60)

        assert (git_repos_dir_module_scope / repository.id / "main").is_dir()
        assert bus.messages == [
            messages.RefreshGitClone(
                meta=Meta(initiator_id=WORKER_IDENTITY),
                repository_id=repository.id,
                repository_name=repository.name.value,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=default_branch.name,
            )
        ]

    async def test_warm_up_broadcasts_even_when_the_fetch_fails(
        self,
        default_branch: Branch,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        existing_copy: None,
        unreachable_upstream: None,
        bus: BusRecorder,
        warm_up: RepositoryWarmUp,
    ) -> None:
        """The fetch only gives this copy a fetch time, so it must not keep other workers without a copy."""
        with capture_logs() as records:
            await warm_up.warm_up(model=self._model(repository=repository, default_branch=default_branch))

        assert _fetch_failures(records=records) == [_fetch_failure(repository=repository)]
        assert bus.messages == [
            messages.RefreshGitClone(
                meta=Meta(initiator_id=WORKER_IDENTITY),
                repository_id=repository.id,
                repository_name=repository.name.value,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=default_branch.name,
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
        """The sync creates this copy along with its first import, so the warm-up neither clones nor broadcasts."""
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
        """A read-only repository with nothing imported is still cloned at the remote head and broadcast to other workers."""
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
        # A clone alone leaves no fetch time, so the copy would report none until the next sync.
        local_copy = Repo(git_repos_dir_module_scope / repository.id / "main")
        assert (Path(local_copy.git_dir) / "FETCH_HEAD").is_file()

    async def test_the_clone_request_leaves_an_existing_fetched_copy_as_it_is(
        self,
        client: InfrahubClient,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        fetched_existing_copy: None,
    ) -> None:
        local_copy = Repo(git_repos_dir_module_scope / repository.id / "main")
        head_before = local_copy.head.commit.hexsha
        worktrees_before = local_copy.git.worktree("list", "--porcelain")
        fetched_before = (Path(local_copy.git_dir) / "FETCH_HEAD").stat().st_mtime_ns

        await repository_operations.clone.fn(message=_clone_request(repository=repository, initiator="another-worker"))

        assert local_copy.head.commit.hexsha == head_before
        assert local_copy.git.worktree("list", "--porcelain") == worktrees_before
        assert (Path(local_copy.git_dir) / "FETCH_HEAD").stat().st_mtime_ns == fetched_before

    async def test_the_clone_request_fetches_an_existing_copy_never_fetched(
        self,
        client: InfrahubClient,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        existing_copy: None,
    ) -> None:
        """Another initialization on this worker may have cloned the copy first, leaving it without a fetch time."""
        local_copy = Repo(git_repos_dir_module_scope / repository.id / "main")
        head_before = local_copy.head.commit.hexsha

        await repository_operations.clone.fn(message=_clone_request(repository=repository, initiator="another-worker"))

        assert local_copy.head.commit.hexsha == head_before
        assert (Path(local_copy.git_dir) / "FETCH_HEAD").is_file()

    async def test_the_clone_request_fetches_a_copy_whose_last_fetch_failed(
        self,
        client: InfrahubClient,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
        cold_worker: None,
        copy_whose_last_fetch_failed: None,
    ) -> None:
        """A failed fetch leaves an empty fetch record, which gives the copy no fetch time."""
        fetch_head = Path(Repo(git_repos_dir_module_scope / repository.id / "main").git_dir) / "FETCH_HEAD"
        assert fetch_head.stat().st_size == 0

        await repository_operations.clone.fn(message=_clone_request(repository=repository, initiator="another-worker"))

        upstream = Repo(git_repos_source_dir_module_scope / "car-dealership")
        fetched = {line.split("\t")[0] for line in fetch_head.read_text().splitlines()}
        assert fetched == {branch.commit.hexsha for branch in upstream.branches}

    async def test_the_clone_request_succeeds_when_the_fetch_fails(
        self,
        client: InfrahubClient,
        repository: CoreRepository,
        git_repos_dir_module_scope: Path,
        cold_worker: None,
        existing_copy: None,
        unreachable_upstream: None,
    ) -> None:
        """The fetch only records a fetch time, so its failure must not fail the request that created the copy."""
        local_copy = Repo(git_repos_dir_module_scope / repository.id / "main")
        head_before = local_copy.head.commit.hexsha

        with capture_logs() as records:
            await repository_operations.clone.fn(
                message=_clone_request(repository=repository, initiator="another-worker")
            )

        assert _fetch_failures(records=records) == [_fetch_failure(repository=repository)]
        assert local_copy.head.commit.hexsha == head_before

    async def test_the_worker_that_sent_the_clone_request_ignores_it(
        self, client: InfrahubClient, repository: CoreRepository, git_repos_dir_module_scope: Path, cold_worker: None
    ) -> None:
        await repository_operations.clone.fn(message=_clone_request(repository=repository, initiator=WORKER_IDENTITY))

        assert not (git_repos_dir_module_scope / repository.id).exists()
