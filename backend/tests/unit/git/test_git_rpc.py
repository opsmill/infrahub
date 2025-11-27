from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self
from unittest.mock import ANY, AsyncMock, patch

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.exceptions import RepositoryError
from infrahub.git import InfrahubRepository
from infrahub.git.models import (
    GitDiffNamesOnly,
    GitRepositoryAdd,
    GitRepositoryAddReadOnly,
    GitRepositoryMerge,
    GitRepositoryPullReadOnly,
)
from infrahub.git.repository import InfrahubReadOnlyRepository
from infrahub.git.tasks import add_git_repository, add_git_repository_read_only, pull_read_only
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_client, build_message_bus, build_workflow
from infrahub.workflows.catalogue import GIT_REPOSITORIES_DIFF_NAMES_ONLY, GIT_REPOSITORIES_MERGE
from tests.adapters.message_bus import BusSimulator
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from types import TracebackType

    from infrahub_sdk.branch import BranchData

    from infrahub.core.node import Node
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
    async def setup(self, dependency_provider):
        self.default_branch_name = "default-branch"
        self.client = AsyncMock(spec=InfrahubClient)
        self.recorder = BusSimulator()
        self.service = await InfrahubServices.new(client=self.client, message_bus=self.recorder)

        with dependency_provider.scope(build_message_bus, lambda: self.recorder):
            self.mock_repo = AsyncMock(spec=InfrahubRepository)
            self.mock_repo = AsyncMock(spec=InfrahubRepository)
            self.mock_repo.default_branch = self.default_branch_name
            self.mock_repo.infrahub_branch_name = self.default_branch_name
            self.mock_repo.internal_status = "active"

            yield

            patch.stopall()

    async def test_git_rpc_create_successful(
        self, prefect_test_fixture, git_upstream_repo_01: dict[str, str], setup
    ) -> None:
        repo_id = str(UUIDT())
        model = GitRepositoryAdd(
            repository_id=repo_id,
            repository_name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            default_branch_name=self.default_branch_name,
            infrahub_branch_name=self.default_branch_name,
            infrahub_branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
            internal_status="active",
        )

        self.mock_repo.import_objects_from_files = AsyncMock()

        with (
            patch("infrahub.git.tasks.lock") as mock_infra_lock,
            patch("infrahub.git.tasks.InfrahubRepository", spec=InfrahubRepository) as mock_repo_class,
        ):
            mock_infra_lock.registry = AsyncMock(spec=InfrahubLockRegistry)
            mock_repo_class.new.return_value = self.mock_repo
            await add_git_repository(model=model)

            mock_infra_lock.registry.get.assert_called_once_with(
                name=git_upstream_repo_01["name"], namespace="repository"
            )

            mock_repo_class.new.assert_awaited_once_with(
                id=repo_id,
                name=git_upstream_repo_01["name"],
                location=str(git_upstream_repo_01["path"]),
                client=ANY,
                infrahub_branch_name=self.default_branch_name,
                internal_status="active",
                default_branch_name=self.default_branch_name,
            )
            self.mock_repo.import_objects_from_files.assert_awaited_once_with(
                infrahub_branch_name=self.default_branch_name, git_branch_name=self.default_branch_name
            )
            self.mock_repo.sync.assert_awaited_once_with()

        assert len(self.recorder.messages) > 0
        assert isinstance(self.recorder.messages[0], RefreshGitFetch)


async def test_git_rpc_merge(
    prefect_test_fixture,
    dependency_provider,
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
        default_branch="main",
        repository_kind=InfrahubKind.REPOSITORY,
    )

    client = InfrahubClient(config=Config(requester=dummy_async_request))
    bus_simulator = await helper.get_message_bus_simulator()
    workflow = WorkflowLocalExecution()
    with (
        dependency_provider.scope(build_client, lambda: client),
        dependency_provider.scope(build_message_bus, lambda: bus_simulator),
        dependency_provider.scope(build_workflow, lambda: workflow),
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
    prefect_test_fixture,
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
        first_commit=commit_branch01,
        second_commit=commit_branch02,
    )

    bus_simulator = await helper.get_message_bus_simulator()
    service = await InfrahubServices.new(
        client=InfrahubClient(), message_bus=bus_simulator, workflow=WorkflowLocalExecution()
    )
    diff = await service.workflow.execute_workflow(
        workflow=GIT_REPOSITORIES_DIFF_NAMES_ONLY, parameters={"model": model}
    )
    assert diff.files_changed == ["README.md", "test_files/sports.yml"]

    model = GitDiffNamesOnly(
        repository_id=str(repo.id),
        repository_name=repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        first_commit=commit_branch01,
        second_commit=commit_main,
    )
    diff = await service.workflow.execute_workflow(
        workflow=GIT_REPOSITORIES_DIFF_NAMES_ONLY, parameters={"model": model}
    )
    assert diff.files_changed == ["test_files/sports.yml"]


class TestAddReadOnly:
    @pytest.fixture
    async def setup(self, dependency_provider):
        self.client = AsyncMock(spec=InfrahubClient)
        self.recorder = BusSimulator()
        self.service = await InfrahubServices.new(client=self.client, message_bus=self.recorder)

        with dependency_provider.scope(build_message_bus, lambda: self.recorder):
            lock_patcher = patch("infrahub.git.tasks.lock")
            self.mock_infra_lock = lock_patcher.start()
            self.mock_infra_lock.registry = AsyncMock(spec=InfrahubLockRegistry)
            repo_class_patcher = patch("infrahub.git.tasks.InfrahubReadOnlyRepository", spec=InfrahubReadOnlyRepository)
            self.mock_repo_class = repo_class_patcher.start()
            self.mock_repo = AsyncMock(spec=InfrahubReadOnlyRepository)
            self.mock_repo_class.new.return_value = self.mock_repo

            yield

            # teardown
            patch.stopall()

    async def test_git_rpc_add_read_only_success(self, git_upstream_repo_01: dict[str, str], setup) -> None:
        repo_id = str(UUIDT())
        model = GitRepositoryAddReadOnly(
            repository_id=repo_id,
            repository_name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            ref="branch01",
            infrahub_branch_name="read-only-branch",
            infrahub_branch_id="469cd407-0a8f-4d4e-9629-84fa435cf5ad",
            internal_status="active",
            client=ANY,
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
        self.mock_repo.import_objects_from_files.assert_awaited_once_with(infrahub_branch_name="read-only-branch")
        self.mock_repo.sync_from_remote.assert_awaited_once_with()

        assert len(self.recorder.messages) > 0
        assert isinstance(self.recorder.messages[0], RefreshGitFetch)


class TestPullReadOnly:
    @pytest.fixture
    async def setup(self, dependency_provider):
        self.client = AsyncMock(spec=InfrahubClient)
        self.recorder = BusSimulator()
        self.workflow = WorkflowLocalExecution()
        self.service = await InfrahubServices.new(client=self.client, workflow=self.workflow, message_bus=self.recorder)

        with (
            dependency_provider.scope(build_message_bus, lambda: self.recorder),
            dependency_provider.scope(build_workflow, lambda: self.workflow),
            dependency_provider.scope(build_client, lambda: self.client),
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

    async def test_improper_message(self, setup) -> None:
        self.model.ref = None
        self.model.commit = None

        await pull_read_only(model=self.model)

        self.mock_repo_class.new.assert_not_awaited()
        self.mock_repo_class.init.assert_not_awaited()

    async def test_existing_repository(self, setup) -> None:
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
            infrahub_branch_name=self.infrahub_branch_name, commit=self.commit
        )
        self.mock_repo.sync_from_remote.assert_awaited_once_with(commit=self.commit)

        assert len(self.recorder.messages) > 0
        assert isinstance(self.recorder.messages[0], RefreshGitFetch)

    async def test_new_repository(self, setup, prefect_test_fixture) -> None:
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
            infrahub_branch_name=self.infrahub_branch_name, commit=self.commit
        )
        self.mock_repo.sync_from_remote.assert_awaited_once_with(commit=self.commit)

        assert len(self.recorder.messages) > 0
        assert isinstance(self.recorder.messages[0], RefreshGitFetch)
