"""An import that stops partway leaves its branch failed, or syncing until the periodic sync imports it again."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreRepository
from infrahub_sdk.uuidt import UUIDT

from infrahub import lock
from infrahub.core.constants import RepositoryInternalStatus, RepositoryOperationalStatus, RepositorySyncStatus
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from infrahub.git.activity.models import RepositoryActivityOperation
from infrahub.git.divergence.suppression import RetargetMarkers
from infrahub.git.models import GitRepositoryAdd
from infrahub.git.sync import RepositoryAdder, RepositoryFileImporter, RepositoryImporter, RepositorySyncer
from infrahub.git.tasks import import_stopped_partway, sync_remote_repositories
from infrahub.workers.dependencies import build_cache
from tests.adapters.cache import MemoryCache, RecordingCache
from tests.adapters.delivery_state import build_idle_delivery_state
from tests.adapters.lock import FailingImporter
from tests.adapters.repository_record_store import build_in_memory_recorder
from tests.helpers.dependency_override import override_dependency
from tests.helpers.flow import call_in_flow
from tests.helpers.git import LocalRemote
from tests.helpers.repository_activity import activity_run, run_record_writes
from tests.helpers.repository_sync import create_repository_node, run_add_flow
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.git.integrator import ObjectImportPlan
    from infrahub.git.repository import PendingObjectImport

TRUNK = "main"
CONFIG_FILES = {".infrahub.yml": "---\n"}
TRUNK_IMPORT: list[tuple[str | None, str | None]] = [("building", TRUNK), ("applying", TRUNK)]


async def create_node(db: InfrahubDatabase, remote: LocalRemote, name: str) -> Node:
    return await create_repository_node(
        db=db,
        name=name,
        location=str(remote.directory),
        default_branch=TRUNK,
        operational_status=RepositoryOperationalStatus.ONLINE.value,
    )


async def recorded_state(client: InfrahubClient, node: Node) -> tuple[str | None, str | None]:
    repository = await client.get(kind=CoreRepository, id=node.id, branch=TRUNK)
    return repository.commit.value, repository.sync_status.value


async def add_and_stop_an_import(
    db: InfrahubDatabase, client: InfrahubClient, tmp_path: Path, name: str
) -> tuple[Node, str]:
    """Add a repository, then leave its default branch as an import that stopped partway leaves it: syncing."""
    remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
    head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
    node = await create_node(db=db, remote=remote, name=name)
    state = await run_add_flow(node=node, name=name, location=str(remote.directory))
    assert state.is_completed()
    repo = await InfrahubRepository.init(
        id=node.id, name=name, client=client, infrahub_branch_name=registry.default_branch
    )
    await repo.record_commit_for_import(branch_name=registry.default_branch, commit=head)
    assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.SYNCING.value)
    return node, head


def add_model(node: Node, name: str, remote: LocalRemote) -> GitRepositoryAdd:
    return GitRepositoryAdd(
        location=str(remote.directory),
        repository_id=node.id,
        repository_name=name,
        infrahub_branch_name=registry.default_branch,
        infrahub_branch_id=str(UUIDT()),
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )


def trunk_imports(cache: RecordingCache, node: Node) -> list[tuple[str | None, str | None]]:
    return [write for write in run_record_writes(cache=cache, repository_id=node.id) if write[1] == TRUNK]


class TestRepairOfAStoppedImport(TestInfrahubApp):
    """A synchronization cycle that finds the default branch left syncing.

    The cycle visits every repository of the stack, so these tests run in a stack of their own.
    """

    async def test_the_cycle_imports_a_default_branch_left_syncing_by_a_stopped_import(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The run of the cycle itself does not count as a run that works on the repository."""
        node, head = await add_and_stop_an_import(db=db, client=client, tmp_path=tmp_path, name="stopped-import")
        cache = RecordingCache()

        with override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider):
            await sync_remote_repositories()

        assert trunk_imports(cache=cache, node=node) == TRUNK_IMPORT
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.IN_SYNC.value)

    async def test_the_cycle_leaves_a_default_branch_syncing_while_another_run_works_on_the_repository(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        node, head = await add_and_stop_an_import(db=db, client=client, tmp_path=tmp_path, name="import-under-way")
        cache = RecordingCache()

        with override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider):
            async with activity_run(repository_id=node.id, cache=cache):
                await sync_remote_repositories()

        assert trunk_imports(cache=cache, node=node) == []
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.SYNCING.value)

    async def test_a_default_branch_the_cycle_read_as_syncing_is_read_again(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The bootstrap can import the branch after the cycle read it, and the repair must not import it a second time."""
        name = "imported-since-the-read"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.IN_SYNC.value)
        repo = await InfrahubRepository.init(
            id=node.id, name=name, client=client, infrahub_branch_name=registry.default_branch
        )

        async with activity_run(repository_id=node.id) as run:
            stopped = await import_stopped_partway(
                repo=repo,
                branch_name=registry.default_branch,
                cycle_status=RepositorySyncStatus.SYNCING.value,
                run=run,
            )

        assert stopped is False


class StateReadingImporter(RepositoryImporter):
    """Read the commit and status of the default branch when its import is built, then import from the object files."""

    def __init__(self, client: InfrahubClient, node: Node) -> None:
        self._client = client
        self._node = node
        self._importer = RepositoryFileImporter()
        self.states_at_build: list[tuple[str | None, str | None]] = []

    async def build_branch_import(
        self, repo: InfrahubRepository, pending_import: PendingObjectImport
    ) -> ObjectImportPlan:
        self.states_at_build.append(await recorded_state(client=self._client, node=self._node))
        return await self._importer.build_branch_import(repo, pending_import)

    async def apply_branch_import(self, repo: InfrahubRepository, plan: ObjectImportPlan) -> None:
        await self._importer.apply_branch_import(repo, plan)


class FailingAfterApplyImporter(RepositoryImporter):
    """Import from the object files, then fail, like a step that runs after every object is imported."""

    def __init__(self) -> None:
        self._importer = RepositoryFileImporter()

    async def build_branch_import(
        self, repo: InfrahubRepository, pending_import: PendingObjectImport
    ) -> ObjectImportPlan:
        return await self._importer.build_branch_import(repo, pending_import)

    async def apply_branch_import(self, repo: InfrahubRepository, plan: ObjectImportPlan) -> None:
        await self._importer.apply_branch_import(repo, plan)
        raise RuntimeError("event bus unavailable")


class TestStatusOfAnImportThatStops(TestInfrahubApp):
    async def test_the_sync_records_a_new_commit_of_the_default_branch_with_its_syncing_mark(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The import is built outside the lock, so a sync that stops before it must leave the branch reading syncing."""
        name = "advanced-trunk"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        imported = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        head = remote.commit(branch_name=TRUNK, files={"data.txt": "v2\n"})
        repo = await InfrahubRepository.init(
            id=node.id, name=name, client=client, infrahub_branch_name=registry.default_branch
        )
        importer = StateReadingImporter(client=client, node=node)
        syncer = RepositorySyncer(
            lock_registry=lock.registry,
            importer=importer,
            recorder=build_in_memory_recorder(),
            retarget_markers=RetargetMarkers(cache=MemoryCache()),
            state=build_idle_delivery_state(repository_id=node.id),
        )

        async with activity_run(repository_id=node.id) as run:
            outcome = await call_in_flow(
                lambda: syncer.sync(repo, activity=run, graph_commits={registry.default_branch: imported})
            )

        assert outcome.failed == ()
        assert importer.states_at_build == [(head, RepositorySyncStatus.SYNCING.value)]
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.IN_SYNC.value)

    async def test_an_import_that_fails_before_it_is_applied_sets_the_branch_failed(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A failure the import's own error handling does not cover, such as taking the lock, must not leave syncing."""
        name = "added-and-stopped"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        adder = RepositoryAdder(
            lock_registry=lock.registry,
            importer=FailingImporter(RuntimeError("lock backend unavailable")),
            client=client,
        )

        async with activity_run(repository_id=node.id, operation=RepositoryActivityOperation.ADD) as run:
            added = await adder.add(add_model(node=node, name=name, remote=remote), activity=run)

        assert added.import_error is not None
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.ERROR_IMPORT.value)

    async def test_a_failure_once_the_import_is_applied_leaves_the_branch_in_sync(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "applied-then-failed"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        adder = RepositoryAdder(lock_registry=lock.registry, importer=FailingAfterApplyImporter(), client=client)

        async with activity_run(repository_id=node.id, operation=RepositoryActivityOperation.ADD) as run:
            added = await adder.add(add_model(node=node, name=name, remote=remote), activity=run)

        assert added.import_error is not None
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.IN_SYNC.value)
