from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, patch

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.uuidt import UUIDT
from typing_extensions import Self

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.git import InfrahubRepository
from infrahub.git.activity.models import RepositoryActivityOperation
from infrahub.git.import_errors import RepositoryImportError
from infrahub.git.models import (
    GitDiffNamesOnly,
    GitRepositoryAdd,
    GitRepositoryAddReadOnly,
    GitRepositoryMerge,
    GitRepositoryPullReadOnly,
)
from infrahub.git.repository import CollectedImports, InfrahubReadOnlyRepository
from infrahub.git.sync import RepositoryAdder
from infrahub.git.tasks import add_git_repository, add_git_repository_read_only, pull_read_only
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_cache, build_client, build_message_bus
from infrahub.workflows.catalogue import GIT_REPOSITORIES_DIFF_NAMES_ONLY, GIT_REPOSITORIES_MERGE
from tests.adapters.cache import RecordingCache
from tests.adapters.lock import LockTimeline, RecordingImporter, RecordingLockRegistry
from tests.adapters.message_bus import BusSimulator, FailingBus
from tests.helpers.dependency_override import override_dependency
from tests.helpers.git import LocalRemote, build_repository_client
from tests.helpers.repository_activity import (
    activity_run,
    last_run_branches,
    run_record_operations,
    run_record_writes,
    stored_run_keys,
)
from tests.helpers.repository_sync import INVALID_YAML_CONFIG, invalid_yaml_config_message
from tests.helpers.test_app import TestInfrahubAppHoldingWorkflows
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    from fast_depends import Provider
    from infrahub_sdk.branch import BranchData

    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import HoldingWorkflowExecution
    from tests.conftest import TestHelper


class AsyncContextManagerMock:
    async def __aenter__(self, *args: Any, **kwargs: Any) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def __call__(self, *args: Any, **kwargs: Any) -> Self:
        return self


class TestAddRepository:
    @pytest.fixture
    async def setup(self, dependency_provider: Provider) -> AsyncGenerator[None, None]:
        self.default_branch_name = "default-branch"
        self.client = AsyncMock(spec=InfrahubClient)
        self.recorder = BusSimulator()
        self.service = await InfrahubServices.new(client=self.client, message_bus=self.recorder)

        with override_dependency(build_message_bus, lambda: self.recorder, dependency_provider=dependency_provider):
            self.mock_repo = AsyncMock(spec=InfrahubRepository)
            self.mock_repo.default_branch = self.default_branch_name
            self.mock_repo.infrahub_branch_name = self.default_branch_name
            self.mock_repo.internal_status = "active"
            self.mock_repo.get_commit_value.return_value = "0123456789abcdef0123456789abcdef01234567"
            yield

            patch.stopall()

    async def test_git_rpc_create_successful(
        self,
        prefect_test_fixture: None,
        git_upstream_repo_01: dict[str, str],
        setup: None,
        recording_lock_timeline: LockTimeline,
    ) -> None:
        repo_id = str(UUIDT())
        model = GitRepositoryAdd(
            repository_id=repo_id,
            repository_name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            infrahub_branch_name=self.default_branch_name,
            infrahub_branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
            internal_status="active",
        )

        self.mock_repo.name = git_upstream_repo_01["name"]
        self.mock_repo.collect_pending_imports = AsyncMock(return_value=CollectedImports())

        with patch("infrahub.git.sync.InfrahubRepository", spec=InfrahubRepository) as mock_repo_class:
            mock_repo_class.new.return_value = self.mock_repo
            await add_git_repository(model=model)

            assert f"repository.{git_upstream_repo_01['name']}" in recording_lock_timeline.acquire_sequence()

            mock_repo_class.new.assert_awaited_once_with(
                id=repo_id,
                name=git_upstream_repo_01["name"],
                location=str(git_upstream_repo_01["path"]),
                client=ANY,
                infrahub_branch_name=self.default_branch_name,
            )
            self.mock_repo.build_import_plan.assert_awaited_once_with(
                infrahub_branch_name=self.default_branch_name,
                git_branch_name=self.default_branch_name,
                commit="0123456789abcdef0123456789abcdef01234567",
            )
            self.mock_repo.apply_import_plan.assert_awaited_once()

        assert len(self.recorder.messages) > 0
        assert isinstance(self.recorder.messages[0], RefreshGitFetch)


async def test_git_rpc_merge(
    prefect_test_fixture: None,
    dependency_provider: Provider,
    git_repo_01: InfrahubRepository,
    branch01: BranchData,
    helper: TestHelper,
    create_test_admin: Node,
) -> None:
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    commit_main_before = repo.get_commit_value(branch_name="main")

    model = GitRepositoryMerge(
        repository_id=str(repo.id),
        repository_name=repo.name,
        source_branch="branch01",
        destination_branch="main",
        destination_branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
        internal_status=RepositoryInternalStatus.ACTIVE.value,
        repository_kind=InfrahubKind.REPOSITORY,
        source_commit=repo.get_commit_value(branch_name=branch01.name),
    )

    client = build_repository_client(
        repository_id=str(repo.id),
        name=repo.name,
        location=repo.get_location(),
        default_branch="main",
        commit=commit_main_before,
    )
    bus_simulator = await helper.get_message_bus_simulator()
    workflow = WorkflowLocalExecution()
    with (
        override_dependency(build_client, lambda: client, dependency_provider=dependency_provider),
        override_dependency(build_message_bus, lambda: bus_simulator, dependency_provider=dependency_provider),
        override_workflow(workflow, dependency_provider=dependency_provider),
    ):
        context = InfrahubContext(
            branch=BranchContext(name=branch01.name, id=branch01.id),
            account=AccountSession(
                authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
            ),
        )
        await workflow.submit_workflow(workflow=GIT_REPOSITORIES_MERGE, context=context, parameters={"model": model})

        commit_main_after = repo.get_commit_value(branch_name="main")

        assert commit_main_before != commit_main_after


async def test_git_rpc_diff(
    prefect_test_fixture: None,
    dependency_provider: Provider,
    register_core_models_schema: None,
    git_repo_01: InfrahubRepository,
    branch01: BranchData,
    branch02: BranchData,
    helper: TestHelper,
) -> None:
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    await repo.create_branch_in_git(branch_name=branch02.name, branch_id=branch02.id)

    commit_main = repo.get_commit_value(branch_name="main", remote=False)
    commit_branch01 = repo.get_commit_value(branch_name=branch01.name, remote=False)
    commit_branch02 = repo.get_commit_value(branch_name=branch02.name, remote=False)

    # Diff Between Branch01 and Branch02
    model = GitDiffNamesOnly(
        repository_id=str(repo.id),
        repository_name=repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        infrahub_branch_name="main",
        first_commit=commit_branch01,
        second_commit=commit_branch02,
    )

    bus_simulator = await helper.get_message_bus_simulator()
    client = build_repository_client(
        repository_id=str(repo.id), name=repo.name, location=repo.get_location(), default_branch="main"
    )
    service = await InfrahubServices.new(client=client, message_bus=bus_simulator, workflow=WorkflowLocalExecution())
    with override_dependency(build_client, lambda: client, dependency_provider=dependency_provider):
        diff = await service.workflow.execute_workflow(
            workflow=GIT_REPOSITORIES_DIFF_NAMES_ONLY, parameters={"model": model}
        )
        assert diff.files_changed == ["README.md", "test_files/sports.yml"]

    model = GitDiffNamesOnly(
        repository_id=str(repo.id),
        repository_name=repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        infrahub_branch_name="main",
        first_commit=commit_branch01,
        second_commit=commit_main,
    )
    with override_dependency(build_client, lambda: client, dependency_provider=dependency_provider):
        diff = await service.workflow.execute_workflow(
            workflow=GIT_REPOSITORIES_DIFF_NAMES_ONLY, parameters={"model": model}
        )
        assert diff.files_changed == ["test_files/sports.yml"]


class TestAddReadOnly:
    @pytest.fixture
    async def setup(self, dependency_provider: Provider) -> AsyncGenerator[None, None]:
        self.client = AsyncMock(spec=InfrahubClient)
        self.recorder = BusSimulator()
        self.service = await InfrahubServices.new(client=self.client, message_bus=self.recorder)

        with override_dependency(build_message_bus, lambda: self.recorder, dependency_provider=dependency_provider):
            lock_patcher = patch("infrahub.git.tasks.lock")
            self.mock_infra_lock = lock_patcher.start()
            self.mock_infra_lock.registry = AsyncMock(spec=InfrahubLockRegistry)
            repo_class_patcher = patch("infrahub.git.tasks.InfrahubReadOnlyRepository", spec=InfrahubReadOnlyRepository)
            self.mock_repo_class = repo_class_patcher.start()
            self.mock_repo = AsyncMock(spec=InfrahubReadOnlyRepository)
            self.mock_repo.ref = "branch01"
            self.mock_repo.get_commit_value.return_value = "0123456789abcdef0123456789abcdef01234567"
            self.mock_repo_class.new.return_value = self.mock_repo

            yield

            # teardown
            patch.stopall()

    async def test_git_rpc_add_read_only_success(self, git_upstream_repo_01: dict[str, str], setup: None) -> None:
        repo_id = str(UUIDT())
        model = GitRepositoryAddReadOnly(
            repository_id=repo_id,
            repository_name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            ref="branch01",
            infrahub_branch_name="read-only-branch",
            infrahub_branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
            internal_status="active",
        )

        self.mock_repo.import_objects_from_files = AsyncMock()

        await add_git_repository_read_only(model=model)

        self.mock_infra_lock.registry.get(name=git_upstream_repo_01["name"], namespace="repository")
        self.mock_repo_class.new.assert_awaited_once_with(
            id=repo_id,
            name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            client=ANY,
            ref="branch01",
            infrahub_branch_name="read-only-branch",
        )
        self.mock_repo.import_objects_from_files.assert_awaited_once_with(
            infrahub_branch_name="read-only-branch", activity_run_id=ANY
        )
        self.mock_repo.sync_from_remote.assert_awaited_once_with(
            commit="0123456789abcdef0123456789abcdef01234567", activity=ANY
        )

        assert len(self.recorder.messages) > 0
        broadcast = self.recorder.messages[0]
        assert isinstance(broadcast, RefreshGitFetch)
        assert broadcast.repository_kind == InfrahubKind.READONLYREPOSITORY


class TestPullReadOnly:
    @pytest.fixture
    async def setup(self, dependency_provider: Provider) -> AsyncGenerator[None, None]:
        self.client = AsyncMock(spec=InfrahubClient)
        self.recorder = BusSimulator()
        self.workflow = WorkflowLocalExecution()
        self.service = await InfrahubServices.new(client=self.client, workflow=self.workflow, message_bus=self.recorder)

        with (
            override_dependency(build_message_bus, lambda: self.recorder, dependency_provider=dependency_provider),
            override_workflow(self.workflow, dependency_provider=dependency_provider),
            override_dependency(build_client, lambda: self.client, dependency_provider=dependency_provider),
        ):
            self.commit = str(UUIDT())
            self.infrahub_branch_name = "read-only-branch"
            self.repo_id = str(UUIDT())
            self.location = "/some/directory/over/here"
            self.repo_name = "dont-update-this-dude"
            self.ref = "stable-branch"

            self.model = GitRepositoryPullReadOnly(
                location=self.location,
                repository_id=self.repo_id,
                repository_name=self.repo_name,
                ref=self.ref,
                commit=self.commit,
                infrahub_branch_name=self.infrahub_branch_name,
                infrahub_branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
            )

            lock_patcher = patch("infrahub.git.tasks.lock")
            self.mock_infra_lock = lock_patcher.start()
            self.mock_infra_lock.registry = AsyncMock(spec=InfrahubLockRegistry)  # TODO fix mock?
            repo_class_patcher = patch("infrahub.git.tasks.InfrahubReadOnlyRepository", spec=InfrahubReadOnlyRepository)
            self.mock_repo_class = repo_class_patcher.start()
            self.mock_repo = AsyncMock(spec=InfrahubReadOnlyRepository)
            self.mock_repo_class.new.return_value = self.mock_repo
            self.mock_repo_class.init.return_value = self.mock_repo

            yield

            # teardown
            patch.stopall()

    async def test_improper_message(self, setup: None) -> None:
        self.model.ref = None
        self.model.commit = None

        await pull_read_only(model=self.model)

        self.mock_repo_class.new.assert_not_awaited()
        self.mock_repo_class.init.assert_not_awaited()

    async def test_existing_repository(self, setup: None) -> None:
        self.mock_repo.import_objects_from_files = AsyncMock()

        await pull_read_only(model=self.model)

        self.mock_infra_lock.registry.get(name=self.repo_name, namespace="repository")
        self.mock_repo_class.init.assert_awaited_once_with(
            id=self.repo_id,
            name=self.repo_name,
            location=self.location,
            client=ANY,
            ref=self.ref,
            infrahub_branch_name=self.infrahub_branch_name,
        )
        self.mock_repo.import_objects_from_files.assert_awaited_once_with(
            infrahub_branch_name=self.infrahub_branch_name, commit=self.commit, activity_run_id=ANY
        )
        self.mock_repo.sync_from_remote.assert_awaited_once_with(commit=self.commit, activity=ANY)

        assert len(self.recorder.messages) > 0
        assert isinstance(self.recorder.messages[0], RefreshGitFetch)

    async def test_new_repository(self, setup: None, prefect_test_fixture: None) -> None:
        self.mock_repo_class.init.side_effect = RepositoryError(self.repo_name, "it is broken")
        self.mock_repo.import_objects_from_files = AsyncMock()

        await pull_read_only(model=self.model)

        self.mock_infra_lock.registry.get(name=self.repo_name, namespace="repository")
        self.mock_repo_class.init.assert_awaited_once_with(
            id=self.repo_id,
            name=self.repo_name,
            location=self.location,
            client=ANY,
            ref=self.ref,
            infrahub_branch_name=self.infrahub_branch_name,
        )
        self.mock_repo_class.new.assert_awaited_once_with(
            id=self.repo_id,
            name=self.repo_name,
            location=self.location,
            client=ANY,
            ref=self.ref,
            infrahub_branch_name=self.infrahub_branch_name,
        )
        self.mock_repo.import_objects_from_files.assert_awaited_once_with(
            infrahub_branch_name=self.infrahub_branch_name, commit=self.commit, activity_run_id=ANY
        )
        self.mock_repo.sync_from_remote.assert_awaited_once_with(commit=self.commit, activity=ANY)

        assert len(self.recorder.messages) > 0
        assert isinstance(self.recorder.messages[0], RefreshGitFetch)


@pytest.mark.usefixtures("git_repos_dir")
async def test_add_git_repository_scopes_import_build_and_apply(
    prefect_test_fixture: None,
    register_core_models_schema: None,
    git_upstream_repo_01: dict[str, str],
) -> None:
    """The default-branch import builds outside the lock and applies under it.

    The lock held for the clone is released before the import is built, and the apply phase
    re-acquires it so that concurrent imports of the same repository are serialized.
    """
    timeline = LockTimeline()
    repository_id = str(UUIDT())
    client = build_repository_client(
        repository_id=repository_id,
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        default_branch="main",
    )
    model = GitRepositoryAdd(
        repository_id=repository_id,
        repository_name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        infrahub_branch_name="main",
        infrahub_branch_id=str(UUIDT()),
        internal_status=RepositoryInternalStatus.INACTIVE.value,
    )

    adder = RepositoryAdder(
        lock_registry=RecordingLockRegistry(timeline=timeline),
        importer=RecordingImporter(timeline),
        client=client,
    )
    async with activity_run(operation=RepositoryActivityOperation.ADD) as run:
        await adder.add(model, activity=run)

    timeline.assert_not_held_at_checkpoint(f"repository.{git_upstream_repo_01['name']}", "build")
    timeline.assert_held_at_checkpoint(f"repository.{git_upstream_repo_01['name']}", "apply")


TRACKED_REF = "release"


class TestReadOnlyRepositoryActivity(TestInfrahubAppHoldingWorkflows):
    """The runs that adding and pulling a read-only repository record in the cache.

    A commit write submits another pull, so each flow runs while the submitted workflows are held.
    """

    async def _create_repository(self, db: InfrahubDatabase, tmp_path: Path, name: str) -> tuple[Node, LocalRemote]:
        """Store a read-only repository whose tracked ref holds one commit of its own, without adding it."""
        remote = LocalRemote.create(directory=tmp_path / name, trunk="main", branches=[])
        remote.commit(branch_name=TRACKED_REF, files={"data.txt": "tracked\n"})
        node = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
        await node.new(db=db, name=name, location=str(remote.directory), ref=TRACKED_REF)
        await node.save(db=db)
        return node, remote

    def _add_model(self, node: Node, remote: LocalRemote) -> GitRepositoryAddReadOnly:
        return GitRepositoryAddReadOnly(
            repository_id=node.id,
            repository_name=node.get_attribute("name").value,
            location=str(remote.directory),
            ref=TRACKED_REF,
            infrahub_branch_name=registry.default_branch,
            infrahub_branch_id=str(UUIDT()),
            internal_status=RepositoryInternalStatus.ACTIVE.value,
        )

    def _pull_model(self, node: Node, remote: LocalRemote, ref: str) -> GitRepositoryPullReadOnly:
        return GitRepositoryPullReadOnly(
            repository_id=node.id,
            repository_name=node.get_attribute("name").value,
            location=str(remote.directory),
            ref=ref,
            infrahub_branch_name=registry.default_branch,
            infrahub_branch_id=str(UUIDT()),
        )

    async def test_adding_a_read_only_repository_records_an_add_run(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        dependency_provider: Provider,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        node, remote = await self._create_repository(db=db, tmp_path=tmp_path, name="activity-add-read-only")
        cache = RecordingCache()

        with (
            override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
            workflow_local.hold(),
        ):
            await add_git_repository_read_only(model=self._add_model(node=node, remote=remote))

        assert run_record_operations(cache=cache, repository_id=node.id) == {"add"}
        assert run_record_writes(cache=cache, repository_id=node.id) == [
            (None, None),
            ("fetching", None),
            ("building", registry.default_branch),
            ("applying", registry.default_branch),
            ("fetching", None),
        ]
        assert stored_run_keys(cache=cache, repository_id=node.id) == []
        assert last_run_branches(cache=cache, repository_id=node.id, operation="add") == [
            {"branch_name": registry.default_branch, "outcome": "imported"}
        ]

    async def test_adding_a_read_only_repository_that_fails_records_the_branch_as_failed(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        dependency_provider: Provider,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "activity-failed-add-read-only"
        node, remote = await self._create_repository(db=db, tmp_path=tmp_path, name=name)
        remote.commit(branch_name=TRACKED_REF, files={".infrahub.yml": INVALID_YAML_CONFIG})
        cache = RecordingCache()

        with (
            override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
            workflow_local.hold(),
            pytest.raises(RepositoryImportError, match=rf"^{re.escape(invalid_yaml_config_message(name))}$"),
        ):
            await add_git_repository_read_only(model=self._add_model(node=node, remote=remote))

        assert run_record_writes(cache=cache, repository_id=node.id) == [
            (None, None),
            ("fetching", None),
            ("building", registry.default_branch),
        ]
        assert stored_run_keys(cache=cache, repository_id=node.id) == []
        assert last_run_branches(cache=cache, repository_id=node.id, operation="add") == [
            {"branch_name": registry.default_branch, "outcome": "failed"}
        ]

    async def test_a_pull_records_its_run_while_it_runs_and_the_branch_as_imported(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        dependency_provider: Provider,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        node, remote = await self._create_repository(db=db, tmp_path=tmp_path, name="activity-pull")
        with workflow_local.hold():
            await add_git_repository_read_only(model=self._add_model(node=node, remote=remote))
        remote.commit(branch_name=TRACKED_REF, files={"data.txt": "advanced\n"})
        cache = RecordingCache()

        with (
            override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
            workflow_local.hold(),
        ):
            await pull_read_only(model=self._pull_model(node=node, remote=remote, ref=TRACKED_REF))

        assert run_record_operations(cache=cache, repository_id=node.id) == {"pull"}
        assert run_record_writes(cache=cache, repository_id=node.id) == [
            (None, None),
            ("fetching", None),
            ("building", registry.default_branch),
            ("applying", registry.default_branch),
            ("building", registry.default_branch),
            ("applying", registry.default_branch),
        ]
        assert stored_run_keys(cache=cache, repository_id=node.id) == []
        assert last_run_branches(cache=cache, repository_id=node.id, operation="pull") == [
            {"branch_name": registry.default_branch, "outcome": "imported"}
        ]

    async def test_a_pull_that_fails_records_the_branch_as_failed(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        dependency_provider: Provider,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        node, remote = await self._create_repository(db=db, tmp_path=tmp_path, name="activity-failed-pull")
        with workflow_local.hold():
            await add_git_repository_read_only(model=self._add_model(node=node, remote=remote))
        cache = RecordingCache()

        with (
            override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
            workflow_local.hold(),
            pytest.raises(ValueError, match=r"^Ref missing not found\.$"),
        ):
            await pull_read_only(model=self._pull_model(node=node, remote=remote, ref="missing"))

        assert run_record_writes(cache=cache, repository_id=node.id) == [(None, None), ("fetching", None)]
        assert stored_run_keys(cache=cache, repository_id=node.id) == []
        assert last_run_branches(cache=cache, repository_id=node.id, operation="pull") == [
            {"branch_name": registry.default_branch, "outcome": "failed"}
        ]

    async def test_an_add_whose_broadcast_fails_records_the_branch_as_imported(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        dependency_provider: Provider,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        node, remote = await self._create_repository(db=db, tmp_path=tmp_path, name="activity-add-failed-broadcast")
        cache = RecordingCache()
        failing_bus = FailingBus()

        with (
            override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
            override_dependency(build_message_bus, lambda: failing_bus, dependency_provider=dependency_provider),
            workflow_local.hold(),
            pytest.raises(ConnectionError, match=r"^The message bus cannot be reached$"),
        ):
            await add_git_repository_read_only(model=self._add_model(node=node, remote=remote))

        assert last_run_branches(cache=cache, repository_id=node.id, operation="add") == [
            {"branch_name": registry.default_branch, "outcome": "imported"}
        ]

    async def test_a_pull_whose_broadcast_fails_records_the_branch_as_imported(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        dependency_provider: Provider,
        workflow_local: HoldingWorkflowExecution,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        node, remote = await self._create_repository(db=db, tmp_path=tmp_path, name="activity-pull-failed-broadcast")
        with workflow_local.hold():
            await add_git_repository_read_only(model=self._add_model(node=node, remote=remote))
        remote.commit(branch_name=TRACKED_REF, files={"data.txt": "advanced\n"})
        cache = RecordingCache()
        failing_bus = FailingBus()

        with (
            override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
            override_dependency(build_message_bus, lambda: failing_bus, dependency_provider=dependency_provider),
            workflow_local.hold(),
            pytest.raises(ConnectionError, match=r"^The message bus cannot be reached$"),
        ):
            await pull_read_only(model=self._pull_model(node=node, remote=remote, ref=TRACKED_REF))

        assert last_run_branches(cache=cache, repository_id=node.id, operation="pull") == [
            {"branch_name": registry.default_branch, "outcome": "imported"}
        ]
