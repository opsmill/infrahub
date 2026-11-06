"""A new repository's default branch is imported once, whichever of the add flow and the periodic sync clones it first."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreRepository
from infrahub_sdk.uuidt import UUIDT

from infrahub import config, lock
from infrahub.core.constants import RepositoryInternalStatus, RepositoryOperationalStatus, RepositorySyncStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreRepository as CoreRepositoryNode
from infrahub.core.registry import registry
from infrahub.events.repository_action import CommitUpdatedEvent
from infrahub.git import InfrahubRepository
from infrahub.git.activity.models import RepositoryActivityOperation
from infrahub.git.constants import UPDATE_SYNC_STATUS_MUTATION
from infrahub.git.models import GitRepositoryAdd
from infrahub.git.sync import RepositoryAdder, RepositoryFileImporter, RepositoryImporter
from infrahub.git.tasks import bootstrap_local_repository, sync_remote_repositories
from infrahub.git.writeback.store import build_intent_store
from infrahub.workers.dependencies import build_cache, build_event_service
from tests.adapters.cache import RecordingCache
from tests.adapters.event import MemoryInfrahubEvent
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
NO_IMPORT: list[tuple[str | None, str | None]] = [(None, None), ("fetching", None)]
ONE_IMPORT: list[tuple[str | None, str | None]] = [
    (None, None),
    ("fetching", None),
    ("building", TRUNK),
    ("applying", TRUNK),
]


@dataclass(frozen=True)
class RecordedStatusCase:
    name: str
    status: RepositorySyncStatus
    """The status of the branch when the fresh clone checks it, next to the commit the clone holds."""
    expected_writes: list[tuple[str | None, str | None]]
    expected_status: RepositorySyncStatus


RECORDED_STATUS_CASES: list[RecordedStatusCase] = [
    RecordedStatusCase(
        name="imported",
        status=RepositorySyncStatus.IN_SYNC,
        expected_writes=NO_IMPORT,
        expected_status=RepositorySyncStatus.IN_SYNC,
    ),
    RecordedStatusCase(
        name="being-imported",
        status=RepositorySyncStatus.SYNCING,
        expected_writes=NO_IMPORT,
        expected_status=RepositorySyncStatus.SYNCING,
    ),
    RecordedStatusCase(
        name="failed-import",
        status=RepositorySyncStatus.ERROR_IMPORT,
        expected_writes=ONE_IMPORT,
        expected_status=RepositorySyncStatus.IN_SYNC,
    ),
    RecordedStatusCase(
        name="status-unknown",
        status=RepositorySyncStatus.UNKNOWN,
        expected_writes=ONE_IMPORT,
        expected_status=RepositorySyncStatus.IN_SYNC,
    ),
]


class StateReadingImporter(RepositoryImporter):
    """Read the commit and status the branch holds when its import is built, then import from the object files."""

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


async def create_node(db: InfrahubDatabase, remote: LocalRemote, name: str) -> Node:
    return await create_repository_node(
        db=db,
        name=name,
        location=str(remote.directory),
        default_branch=remote.trunk,
        operational_status=RepositoryOperationalStatus.ONLINE.value,
    )


async def recorded_state(client: InfrahubClient, node: Node, branch: str = TRUNK) -> tuple[str | None, str | None]:
    repository = await client.get(kind=CoreRepository, id=node.id, branch=branch)
    return repository.commit.value, repository.sync_status.value


def commit_events(events: MemoryInfrahubEvent) -> list[tuple[str, str]]:
    return [(event.commit, event.repository_id) for event in events.events if isinstance(event, CommitUpdatedEvent)]


def use_another_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker: str) -> None:
    """Point the repositories directory at an empty one, as on a worker that holds no copy of the repository."""
    directory = tmp_path / worker
    directory.mkdir()
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(directory))


def add_model(node: Node, name: str, remote: LocalRemote, infrahub_branch_name: str | None = None) -> GitRepositoryAdd:
    return GitRepositoryAdd(
        location=str(remote.directory),
        repository_id=node.id,
        repository_name=name,
        infrahub_branch_name=infrahub_branch_name or registry.default_branch,
        infrahub_branch_id=str(UUIDT()),
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )


class TestFreshCloneImport(TestInfrahubApp):
    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in RECORDED_STATUS_CASES])
    async def test_a_fresh_clone_imports_the_default_branch_only_when_the_graph_lacks_its_objects(
        self,
        case: RecordedStatusCase,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        tmp_path: Path,
        git_repos_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        name = f"added-then-cloned-{case.name}"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        added = await InfrahubRepository.init(
            id=node.id, name=name, client=client, infrahub_branch_name=registry.default_branch
        )
        match case.status:
            case RepositorySyncStatus.SYNCING:
                await added.record_commit_for_import(branch_name=registry.default_branch, commit=head)
            case RepositorySyncStatus.ERROR_IMPORT:
                await added.record_import_failure(infrahub_branch_name=registry.default_branch)
            case RepositorySyncStatus.UNKNOWN:
                await client.execute_graphql(
                    query=UPDATE_SYNC_STATUS_MUTATION,
                    variables={"repo_id": node.id, "status": RepositorySyncStatus.UNKNOWN.value},
                    branch_name=registry.default_branch,
                )
            case _:
                pass
        assert await recorded_state(client=client, node=node) == (head, case.status.value)
        use_another_worker(tmp_path=tmp_path, monkeypatch=monkeypatch, worker="fresh-worker")
        repository = await client.get(kind=CoreRepository, id=node.id)
        delivery_state = await build_intent_store(db=db, lock_registry=lock.registry)
        cache = RecordingCache()
        events = MemoryInfrahubEvent()

        with override_dependency(build_event_service, lambda: events, dependency_provider=dependency_provider):
            async with activity_run(repository_id=node.id, cache=cache) as run:
                bootstrapped = await call_in_flow(
                    lambda: bootstrap_local_repository(
                        repo_name=name,
                        repository=repository,
                        infrahub_branch=registry.default_branch,
                        branch_accepts_commit=True,
                        client=client,
                        state=delivery_state,
                        activity=run,
                    )
                )

        assert bootstrapped is not None
        assert bootstrapped.recorded_commit == head
        assert run_record_writes(cache=cache, repository_id=node.id) == case.expected_writes
        assert await recorded_state(client=client, node=node) == (head, case.expected_status.value)
        assert commit_events(events) == []

    async def test_the_add_flow_skips_the_import_of_a_commit_a_fresh_clone_imported(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        tmp_path: Path,
        git_repos_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The periodic sync can clone and import a new repository before its add flow runs on another worker."""
        name = "cloned-then-added"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        repository = await client.get(kind=CoreRepository, id=node.id)
        delivery_state = await build_intent_store(db=db, lock_registry=lock.registry)
        adder = RepositoryAdder(lock_registry=lock.registry, importer=RepositoryFileImporter(), client=client)
        cache = RecordingCache()
        events = MemoryInfrahubEvent()

        with override_dependency(build_event_service, lambda: events, dependency_provider=dependency_provider):
            async with activity_run(repository_id=node.id) as run:
                bootstrapped = await call_in_flow(
                    lambda: bootstrap_local_repository(
                        repo_name=name,
                        repository=repository,
                        infrahub_branch=registry.default_branch,
                        branch_accepts_commit=True,
                        client=client,
                        state=delivery_state,
                        activity=run,
                    )
                )
            assert bootstrapped is not None
            use_another_worker(tmp_path=tmp_path, monkeypatch=monkeypatch, worker="add-worker")
            async with activity_run(
                repository_id=node.id, operation=RepositoryActivityOperation.ADD, cache=cache
            ) as run:
                added = await adder.add(add_model(node=node, name=name, remote=remote), activity=run)

        assert added.import_error is None
        assert run_record_writes(cache=cache, repository_id=node.id) == NO_IMPORT
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.IN_SYNC.value)
        assert commit_events(events) == [(head, node.id)]

    async def test_the_add_flow_marks_the_branch_syncing_before_it_releases_the_lock(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The import is built outside the lock, so a clone that takes the lock first must already see it under way."""
        name = "added-and-marked"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        importer = StateReadingImporter(client=client, node=node)
        adder = RepositoryAdder(lock_registry=lock.registry, importer=importer, client=client)

        async with activity_run(repository_id=node.id, operation=RepositoryActivityOperation.ADD) as run:
            added = await adder.add(add_model(node=node, name=name, remote=remote), activity=run)

        assert added.import_error is None
        assert importer.states_at_build == [(head, RepositorySyncStatus.SYNCING.value)]
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.IN_SYNC.value)

    async def test_the_add_flow_sets_the_status_only_of_the_branch_it_imports_into(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """Holds when the Infrahub branch is named like the repository's default branch, which maps to another branch."""
        name = "added-on-develop"
        develop = "develop"
        await create_branch(branch_name=develop, db=db)
        remote = LocalRemote.create(directory=tmp_path / name, trunk=develop, branches=[])
        remote.commit(branch_name=develop, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        adder = RepositoryAdder(lock_registry=lock.registry, importer=RepositoryFileImporter(), client=client)
        model = add_model(node=node, name=name, remote=remote, infrahub_branch_name=develop)

        async with activity_run(repository_id=node.id, operation=RepositoryActivityOperation.ADD) as run:
            added = await adder.add(model, activity=run)

        assert added.import_error is None
        _, develop_status = await recorded_state(client=client, node=node, branch=develop)
        _, default_status = await recorded_state(client=client, node=node, branch=TRUNK)
        assert (develop_status, default_status) == (
            RepositorySyncStatus.IN_SYNC.value,
            RepositorySyncStatus.UNKNOWN.value,
        )


class TestSynchronisationCycleOnAFreshWorker(TestInfrahubApp):
    """A synchronization cycle on a worker that holds no copy of the repository.

    The cycle visits every repository of the stack, so these tests run in a stack of their own.
    """

    async def test_the_cycle_imports_the_default_branch_of_a_new_repository_once(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        dependency_provider: Provider,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "new-in-cycle"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        head = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        cache = RecordingCache()

        with override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider):
            await sync_remote_repositories()

        assert run_record_writes(cache=cache, repository_id=node.id) == [*ONE_IMPORT, ("fetching", None)]
        assert await recorded_state(client=client, node=node) == (head, RepositorySyncStatus.IN_SYNC.value)

    async def test_the_cycle_records_a_rewrite_of_the_trunk_that_a_fresh_clone_holds(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The seed import records the rewritten commit, and the syncer still classifies it against the earlier one."""
        name = "rewritten-for-fresh-worker"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        imported = remote.commit(branch_name=TRUNK, files=CONFIG_FILES)
        node = await create_node(db=db, remote=remote, name=name)
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        rewritten = remote.commit(branch_name=TRUNK, files={"data.txt": "rewritten\n"}, amend=True)
        use_another_worker(tmp_path=tmp_path, monkeypatch=monkeypatch, worker="fresh-worker")

        await sync_remote_repositories()

        recorded = await NodeManager.get_one(
            db=db, id=node.id, kind=CoreRepositoryNode, branch=registry.default_branch, raise_on_error=True
        )
        assert (
            recorded.commit.value,
            recorded.last_rewrite_previous_commit.value,
            recorded.last_rewrite_commit.value,
            recorded.rewrite_count.value,
        ) == (rewritten, imported, rewritten, 1)
