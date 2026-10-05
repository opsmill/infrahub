import logging
import shutil
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from git import Repo
from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreRepository
from infrahub_sdk.uuidt import UUIDT
from prefect import flow
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import State

from infrahub import config, lock
from infrahub.core.constants import (
    InfrahubKind,
    RepositoryInternalStatus,
    RepositoryOperationalStatus,
    RepositorySyncStatus,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreRepository as CoreRepositoryNode
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import RepositoryError
from infrahub.git import InfrahubRepository
from infrahub.git.sync import (
    RepositoryBranchesFailedError,
    RepositoryFileImporter,
    RepositorySyncer,
    SyncOutcome,
    SyncReport,
)
from infrahub.git.tasks import sync_repository_from_origin
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.message_bus.messages.refresh_git_fetch import BranchCommitPair
from infrahub.workers.dependencies import clear_singletons
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag
from tests.adapters.message_bus import BusRecorder, BusSimulator
from tests.conftest import TestHelper
from tests.helpers.git import LocalRemote, build_repository_client, clone_repository
from tests.helpers.repository_sync import (
    FLOW_RUN_LOGGER,
    INVALID_YAML_CONFIG,
    create_repository_node,
    flow_run_tags,
    invalid_yaml_config_message,
    is_linked_to_node,
    run_add_flow,
    run_sync_flow,
    skipped_branch_warning,
    skipped_branch_warnings,
)
from tests.helpers.test_app import TestInfrahubApp


@dataclass
class SyncScenario:
    name: str
    git_default_branch: str
    staging_branch: str | None
    active_internal_status: str


SCENARIOS = [
    # Git default branch matches Infrahub's default; no staging branch.
    SyncScenario(
        name="active_matching_default",
        git_default_branch="main",
        staging_branch=None,
        active_internal_status=RepositoryInternalStatus.ACTIVE.value,
    ),
    # Git default branch differs from Infrahub's default.
    SyncScenario(
        name="active_mismatched_default",
        git_default_branch="production",
        staging_branch=None,
        active_internal_status=RepositoryInternalStatus.ACTIVE.value,
    ),
    # Staging sync; git default branch matches Infrahub's default.
    SyncScenario(
        name="staging_matching_default",
        git_default_branch="main",
        staging_branch="staging-x",
        active_internal_status=RepositoryInternalStatus.STAGING.value,
    ),
    # Staging sync; git default branch differs from Infrahub's default.
    SyncScenario(
        name="staging_mismatched_default",
        git_default_branch="production",
        staging_branch="staging-x",
        active_internal_status=RepositoryInternalStatus.STAGING.value,
    ),
]


@pytest.fixture
def message_bus_recorder(helper: TestHelper) -> Generator[BusRecorder, None, None]:
    """Install a recording bus and drop cached singletons so the flow resolves it, restoring on exit."""
    original = config.OVERRIDE.message_bus
    recorder = helper.get_message_bus_recorder()
    config.OVERRIDE.message_bus = recorder
    clear_singletons()
    yield recorder
    config.OVERRIDE.message_bus = original
    clear_singletons()


async def _build_repository(
    db: InfrahubDatabase, source_dir: Path, git_default_branch: str, internal_status: str
) -> tuple[Node, InfrahubRepository]:
    """Seed a repository node and clone it locally, with the given git default branch and status."""
    upstream = Repo.init(source_dir, initial_branch=git_default_branch)
    (source_dir / "file.txt").write_text("content")
    upstream.index.add(["file.txt"])
    upstream.index.commit("First commit")

    node = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await node.new(
        db=db,
        name="test-repository",
        location=str(source_dir),
        default_branch=git_default_branch,
        internal_status=internal_status,
    )
    await node.save(db=db)

    client = build_repository_client(
        repository_id=node.id,
        name="test-repository",
        location=str(source_dir),
        default_branch=git_default_branch,
        internal_status=RepositoryInternalStatus(internal_status),
        query_branches=("main", "staging-x"),
    )
    repo = await clone_repository(
        id=node.id,
        name="test-repository",
        location=str(source_dir),
        default_branch=git_default_branch,
        internal_status=RepositoryInternalStatus(internal_status),
        client=client,
        update_commit_value=False,
    )
    return node, repo


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario.name for scenario in SCENARIOS])
async def test_sync_broadcasts_synced_commit(
    scenario: SyncScenario,
    db: InfrahubDatabase,
    register_core_models_schema: None,
    tmp_path: Path,
    git_repos_dir: Path,
    prefect_test_fixture: None,
    message_bus_recorder: BusRecorder,
) -> None:
    """The trunk broadcast to the worker pool resolves to the repository's git default branch HEAD.

    Holds across matching and mismatched default branches and staging syncs, so every worker
    converges on the same pinned commit, including on a cycle that advanced nothing.
    """
    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    node, repo = await _build_repository(
        db=db,
        source_dir=source_dir,
        git_default_branch=scenario.git_default_branch,
        internal_status=scenario.active_internal_status,
    )

    assert repo.client is not None
    client = repo.client
    infrahub_branch = scenario.staging_branch or registry.default_branch

    @flow(name="test-sync-repository-from-origin")
    async def _run_sync() -> None:
        await sync_repository_from_origin(
            repository=node,
            repo=repo,
            staging_branch=scenario.staging_branch,
            infrahub_branch=infrahub_branch,
            default_branch_id="default-branch-id",
            client=client,
        )

    await _run_sync()

    fetch_messages = [message for message in message_bus_recorder.messages if isinstance(message, RefreshGitFetch)]
    assert len(fetch_messages) == 1

    # A staging sync still names the Infrahub default branch, which is where the other workers keep the trunk.
    trunk = BranchCommitPair(
        infrahub_branch_name=registry.default_branch,
        infrahub_branch_id="default-branch-id",
        commit=repo.get_commit_value(branch_name=repo.default_branch, remote=False),
    )
    message = fetch_messages[0]
    assert (message.infrahub_branch_name, message.infrahub_branch_id, message.commit) == (
        trunk.infrahub_branch_name,
        trunk.infrahub_branch_id,
        trunk.commit,
    )
    assert message.branches == (trunk,)


TRUNK = "develop"


@dataclass
class FailedReadCase:
    name: str
    operational_status: str
    expected_linked: bool


FAILED_READ_CASES = [
    FailedReadCase(
        name="online_repository", operational_status=RepositoryOperationalStatus.ONLINE.value, expected_linked=True
    ),
    FailedReadCase(
        name="repository_already_in_error",
        operational_status=RepositoryOperationalStatus.ERROR.value,
        expected_linked=False,
    ),
]

OPERATIONAL_STATUSES = [RepositoryOperationalStatus.ONLINE.value, RepositoryOperationalStatus.ERROR.value]


def run_tags(branches: list[str], node_id: str) -> set[str]:
    """The complete tag set of a sync run linked to one repository and tagged with these branches."""
    return {
        TAG_NAMESPACE,
        WorkflowTag.RELATED_NODE.render(identifier=node_id),
        *(WorkflowTag.BRANCH.render(identifier=branch) for branch in branches),
    }


class TestSkippedBranchTaskLog(TestInfrahubApp):
    """A remote branch named like Infrahub's default branch is reported in the repository's task log.

    The repository's trunk is not Infrahub's default branch, and the remote also carries a branch named
    like Infrahub's default branch, which is the one that collides.
    """

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect: str) -> AsyncGenerator[PrefectClient, None]:
        async with get_client(sync_client=False) as client:
            yield client

    @pytest.fixture(autouse=True)
    def no_import_sync_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every remote branch is a candidate for import, whatever the environment configures."""
        monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])

    @pytest.fixture(autouse=True)
    def capture_run_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING, logger=FLOW_RUN_LOGGER)

    @pytest.fixture(autouse=True)
    def infrahub_default_branch_is_main(self, initialize_registry: None) -> None:
        """Every remote below carries a `main` branch, which only collides while that is Infrahub's default."""
        assert registry.default_branch == "main"

    @pytest.fixture
    def fresh_worker_dir(self, git_repos_dir: Path, tmp_path: Path) -> Generator[Path, None, None]:
        """An empty repositories directory for the test to switch to, restored before the regular one is."""
        directory = tmp_path / "fresh-worker-repositories"
        directory.mkdir()
        original = config.SETTINGS.git.repositories_directory
        yield directory
        config.SETTINGS.git.repositories_directory = original

    async def _connect(
        self, db: InfrahubDatabase, tmp_path: Path, name: str, branches: list[str], head: str | None = None
    ) -> tuple[LocalRemote, Node, State]:
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=branches, head=head)
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch=TRUNK,
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        return remote, node, state

    async def test_connect_records_one_warning(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        _, _, state = await self._connect(db=db, tmp_path=tmp_path, name="connect-repo", branches=["main"])

        assert skipped_branch_warnings(caplog, state) == [
            skipped_branch_warning(branch_name="main", repository_name="connect-repo", default_branch=TRUNK)
        ]

    async def test_connect_records_the_warning_when_the_remote_head_is_the_colliding_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The clone checks the remote's HEAD out as a local branch, which must not hide the collision."""
        name = "connect-head-repo"
        _, _, state = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"], head="main")

        assert skipped_branch_warnings(caplog, state) == [
            skipped_branch_warning(branch_name="main", repository_name=name, default_branch=TRUNK)
        ]

    async def test_connect_records_the_warning_when_another_branch_fails(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A first sync that fails on some other branch still reports the skipped branch before failing."""
        name = "connect-failing-repo"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=["main"])
        remote.commit(branch_name="broken", files={".infrahub.yml": "schemas: [unclosed\n"})
        await create_branch(branch_name="broken", db=db)
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch=TRUNK,
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )

        state = await run_add_flow(node=node, name=name, location=str(remote.directory))

        assert state.is_failed()
        error = await state.aresult(raise_on_failure=False)
        assert isinstance(error, RepositoryBranchesFailedError)
        assert error.message.startswith(
            f"Unable to synchronize the following branches of repository {name}: broken (step=import): "
        )
        assert error.report == SyncReport(
            skipped_branches=("main",),
            imported_branches=(),
            failed_import_branches=("broken",),
            advanced_skipped_branches=(),
        )
        assert skipped_branch_warnings(caplog, state) == [
            skipped_branch_warning(branch_name="main", repository_name=name, default_branch=TRUNK)
        ]

    async def test_cycles_report_only_when_something_moved(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """Idle cycles stay silent; an import or a commit on the skipped branch each report once.

        The second and third cycles pair up: one imports a changed trunk, the other imports nothing and
        only sees the skipped branch move, and each reports the skipped branch for that reason alone.
        """
        name = "cycling-repo"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        location = str(remote.directory)
        expected_warning = [skipped_branch_warning(branch_name="main", repository_name=name, default_branch=TRUNK)]

        idle = await run_sync_flow(client=client, repository_id=node.id, name=name, location=location)
        assert idle.is_completed()
        assert skipped_branch_warnings(caplog, idle) == []
        assert not await is_linked_to_node(prefect_client, idle, node.id)

        remote.commit(branch_name=TRUNK, files={"data.txt": "trunk v2\n"})
        imported = await run_sync_flow(client=client, repository_id=node.id, name=name, location=location)
        assert imported.is_completed()
        assert skipped_branch_warnings(caplog, imported) == expected_warning

        remote.commit(branch_name="main", files={"data.txt": "main v2\n"})
        advanced = await run_sync_flow(client=client, repository_id=node.id, name=name, location=location)
        assert advanced.is_completed()
        assert skipped_branch_warnings(caplog, advanced) == expected_warning
        # Nothing was imported, so only reporting the skipped branch can have linked this run.
        assert await is_linked_to_node(prefect_client, advanced, node.id)

        idle_again = await run_sync_flow(client=client, repository_id=node.id, name=name, location=location)
        assert idle_again.is_completed()
        assert skipped_branch_warnings(caplog, idle_again) == []
        assert not await is_linked_to_node(prefect_client, idle_again, node.id)

    async def test_colliding_branch_pushed_after_connect_is_reported(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "late-collision-repo"
        remote, node, connect = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=[])
        remote.create_branch("main")

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        assert skipped_branch_warnings(caplog, connect) == []
        assert skipped_branch_warnings(caplog, state) == [
            skipped_branch_warning(branch_name="main", repository_name=name, default_branch=TRUNK)
        ]
        # Nothing was imported, so only reporting the skipped branch can have linked this run.
        assert await flow_run_tags(prefect_client, state) == run_tags(branches=["main"], node_id=node.id)

    async def test_first_sync_on_a_fresh_worker_does_not_report_an_unchanged_colliding_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        fresh_worker_dir: Path,
    ) -> None:
        """The worker clones before the sync reads the remote heads, so the branch is not new to it."""
        name = "fresh-worker-repo"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        config.SETTINGS.git.repositories_directory = str(fresh_worker_dir)

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        assert skipped_branch_warnings(caplog, state) == []
        assert not await is_linked_to_node(prefect_client, state, node.id)

    async def test_idle_sync_reports_no_import_and_no_advance(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "idle-report-repo"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        repo = await InfrahubRepository.init(
            id=node.id,
            name=name,
            location=str(remote.directory),
            client=client,
            infrahub_branch_name=registry.default_branch,
        )

        outcome = await RepositorySyncer(lock_registry=lock.registry, importer=RepositoryFileImporter()).sync(repo)

        assert outcome == SyncOutcome(
            report=SyncReport(
                skipped_branches=("main",),
                imported_branches=(),
                failed_import_branches=(),
                advanced_skipped_branches=(),
            ),
            reconciled=(),
            failed=(),
        )

    async def test_no_warning_once_the_colliding_branch_is_deleted(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "deleted-collision-repo"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        remote.delete_branch("main")
        remote.commit(branch_name=TRUNK, files={"data.txt": "trunk v2\n"})

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        assert skipped_branch_warnings(caplog, state) == []
        # The import links the run by itself, which shows the silence is not an idle cycle's.
        assert await is_linked_to_node(prefect_client, state, node.id)

    async def test_no_warning_once_the_trunk_is_the_infrahub_default_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        fresh_worker_dir: Path,
    ) -> None:
        """Once `main` is the trunk it is imported like any trunk, so a cycle that imports it reports nothing.

        The clone is taken fresh on the new trunk, as a worker that never saw the old one would have it.
        """
        name = "retrunked-repo"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        repository = await client.get(kind=CoreRepository, id=node.id)
        repository.default_branch.value = "main"
        await repository.save()
        await create_branch(branch_name=TRUNK, db=db)

        config.SETTINGS.git.repositories_directory = str(fresh_worker_dir)
        await InfrahubRepository.init(
            id=node.id,
            name=name,
            location=str(remote.directory),
            client=client,
            infrahub_branch_name=registry.default_branch,
        )
        remote.commit(branch_name="main", files={"data.txt": "main v2\n"})

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        assert skipped_branch_warnings(caplog, state) == []
        assert await is_linked_to_node(prefect_client, state, node.id)

    async def test_no_warning_without_a_colliding_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "no-collision-repo"
        remote, node, connect = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=[])
        remote.commit(branch_name=TRUNK, files={"data.txt": "trunk v2\n"})

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        assert skipped_branch_warnings(caplog, connect) == []
        assert skipped_branch_warnings(caplog, state) == []
        assert await is_linked_to_node(prefect_client, state, node.id)

    @pytest.mark.parametrize("operational_status", OPERATIONAL_STATUSES)
    async def test_cycle_that_imports_one_branch_and_fails_another_reports_the_skipped_branch(
        self,
        operational_status: str,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The warning does not depend on the repository being online, and no branch loses its tag.

        One branch fails with an expected error and another with an unrecognised one, and neither
        stops the import of the trunk.
        """
        name = f"partly-failing-cycle-repo-{operational_status}"
        failing_branch = f"broken-on-cycle-{operational_status}"
        unexpected_branch = f"unexpected-on-cycle-{operational_status}"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        await create_branch(branch_name=failing_branch, db=db)
        await create_branch(branch_name=unexpected_branch, db=db)
        remote.commit(branch_name=failing_branch, files={".infrahub.yml": INVALID_YAML_CONFIG})
        remote.commit(
            branch_name=unexpected_branch,
            files={
                ".infrahub.yml": "python_transforms:\n  - name: broken\n    file_path: transform.py\n    class_name: Broken\n",
                "transform.py": 'raise RuntimeError("transform module failed to load")\n',
            },
        )
        remote.commit(branch_name=TRUNK, files={"data.txt": "trunk v2\n"})

        state = await run_sync_flow(
            client=client,
            repository_id=node.id,
            name=name,
            location=str(remote.directory),
            operational_status=operational_status,
        )

        assert state.is_failed()
        error = await state.aresult(raise_on_failure=False)
        assert isinstance(error, RepositoryBranchesFailedError)
        assert error.report.skipped_branches == ("main",)
        assert error.report.imported_branches == ("main",)
        assert sorted(error.report.failed_import_branches) == sorted([failing_branch, unexpected_branch])
        assert error.report.advanced_skipped_branches == ()
        assert error.message == (
            f"Unable to synchronize the following branches of repository {name}: "
            f"{failing_branch} (step=import): {invalid_yaml_config_message(name)}; "
            f"{unexpected_branch} (step=import): Python transform 'broken' (transform.py): "
            "RuntimeError: transform module failed to load"
        )
        sync_statuses = {
            branch_name: (await client.get(kind=CoreRepository, id=node.id, branch=branch_name)).sync_status.value
            for branch_name in ("main", failing_branch, unexpected_branch)
        }
        assert sync_statuses == {
            "main": RepositorySyncStatus.IN_SYNC.value,
            failing_branch: RepositorySyncStatus.ERROR_IMPORT.value,
            unexpected_branch: RepositorySyncStatus.ERROR_IMPORT.value,
        }
        assert skipped_branch_warnings(caplog, state) == [
            skipped_branch_warning(branch_name="main", repository_name=name, default_branch=TRUNK)
        ]
        assert await flow_run_tags(prefect_client, state) == run_tags(
            branches=["main", failing_branch, unexpected_branch], node_id=node.id
        )

    async def test_failed_cycle_where_nothing_else_moved_does_not_report_the_skipped_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The failure links the run while the repository is online, but it is not a reason to report."""
        name = "failing-trunk-cycle-repo"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        remote.commit(branch_name=TRUNK, files={".infrahub.yml": "schemas: [unclosed\n"})

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_failed()
        error = await state.aresult(raise_on_failure=False)
        assert isinstance(error, RepositoryBranchesFailedError)
        assert error.report == SyncReport(
            skipped_branches=("main",),
            imported_branches=(),
            failed_import_branches=("main",),
            advanced_skipped_branches=(),
        )
        assert skipped_branch_warnings(caplog, state) == []
        assert await flow_run_tags(prefect_client, state) == run_tags(branches=["main"], node_id=node.id)

    @pytest.mark.parametrize("case", FAILED_READ_CASES, ids=[case.name for case in FAILED_READ_CASES])
    async def test_failed_fetch_links_the_run_while_online(
        self,
        case: FailedReadCase,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A remote that disappears fails the sync itself, after the repository object was built."""
        name = f"vanished-remote-repo-{case.name}"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        shutil.rmtree(remote.directory)

        state = await run_sync_flow(
            client=client,
            repository_id=node.id,
            name=name,
            location=str(remote.directory),
            operational_status=case.operational_status,
        )

        assert state.is_failed()
        error = await state.aresult(raise_on_failure=False)
        assert isinstance(error, RepositoryError)
        assert not isinstance(error, RepositoryBranchesFailedError)
        assert skipped_branch_warnings(caplog, state) == []
        assert await is_linked_to_node(prefect_client, state, node.id) is case.expected_linked

    async def test_reporting_the_skipped_branch_keeps_the_tags_of_the_imported_branches(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "feature-import-repo"
        remote, node, _ = await self._connect(db=db, tmp_path=tmp_path, name=name, branches=["main"])
        await create_branch(branch_name="feature-import", db=db)
        remote.commit(branch_name="feature-import", files={"data.txt": "feature\n"})

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        assert skipped_branch_warnings(caplog, state) == [
            skipped_branch_warning(branch_name="main", repository_name=name, default_branch=TRUNK)
        ]
        assert await flow_run_tags(prefect_client, state) == run_tags(
            branches=["main", "feature-import"], node_id=node.id
        )

    @pytest.mark.parametrize("case", FAILED_READ_CASES, ids=[case.name for case in FAILED_READ_CASES])
    async def test_failing_node_read_links_the_run_while_online(
        self,
        case: FailedReadCase,
        client: InfrahubClient,
        initialize_registry: None,
        prefect_client: PrefectClient,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """A repository whose node cannot be read fails the run, which is linked to it like any sync failure."""
        repository_id = str(UUIDT())

        state = await run_sync_flow(
            client=client,
            repository_id=repository_id,
            name="unreadable-repo",
            location=str(tmp_path / "missing-remote"),
            operational_status=case.operational_status,
        )

        assert state.is_failed()
        assert isinstance(await state.aresult(raise_on_failure=False), RepositoryError)
        assert await is_linked_to_node(prefect_client, state, repository_id) is case.expected_linked


class TestSynchronisationCycleFailures(TestInfrahubApp):
    """A synchronization cycle in which some branches fail, against a remote whose trunk is `main`."""

    @pytest.fixture(autouse=True)
    def no_import_sync_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every remote branch is a candidate for import, whatever the environment configures."""
        monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])

    async def _connect(self, db: InfrahubDatabase, tmp_path: Path, name: str) -> tuple[LocalRemote, Node]:
        remote = LocalRemote.create(directory=tmp_path / name, trunk="main", branches=[])
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch="main",
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        return remote, node

    async def test_a_failed_branch_does_not_hold_back_the_message_for_the_advanced_branches(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        bus_simulator: BusSimulator,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = "partly-failing-broadcast-repo"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        await create_branch(branch_name="broken-branch", db=db)
        await create_branch(branch_name="healthy-branch", db=db)
        remote.commit(branch_name="broken-branch", files={".infrahub.yml": "schemas: [unclosed\n"})
        healthy_commit = remote.commit(branch_name="healthy-branch", files={"data.txt": "healthy\n"})
        branches = await client.branch.all()
        repo = await InfrahubRepository.init(
            id=node.id,
            name=name,
            location=str(remote.directory),
            client=client,
            infrahub_branch_name=registry.default_branch,
        )
        sent_before = len(bus_simulator.messages)

        @flow(name="test-sync-a-partly-failing-repository")
        async def _run_sync() -> None:
            await sync_repository_from_origin(
                repository=node,
                repo=repo,
                staging_branch=None,
                infrahub_branch=registry.default_branch,
                default_branch_id=branches[registry.default_branch].id,
                client=client,
            )

        await _run_sync()

        fetch_messages = [
            message for message in bus_simulator.messages[sent_before:] if isinstance(message, RefreshGitFetch)
        ]
        assert [message.branches for message in fetch_messages] == [
            (
                BranchCommitPair(
                    infrahub_branch_name=registry.default_branch,
                    infrahub_branch_id=branches[registry.default_branch].id,
                    commit=repo.get_commit_value(branch_name="main", remote=False),
                ),
                BranchCommitPair(
                    infrahub_branch_name="healthy-branch",
                    infrahub_branch_id=branches["healthy-branch"].id,
                    commit=healthy_commit,
                ),
            )
        ]

    async def test_a_failed_default_branch_is_logged_as_an_error_and_recorded_without_being_raised(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        """The trunk fails while it is collected, where no import has recorded anything yet."""
        caplog.set_level(logging.INFO, logger=FLOW_RUN_LOGGER)
        name = "failing-trunk-collection-repo"
        remote, node = await self._connect(db=db, tmp_path=tmp_path, name=name)
        repo = await InfrahubRepository.init(
            id=node.id,
            name=name,
            location=str(remote.directory),
            client=client,
            infrahub_branch_name=registry.default_branch,
        )
        advanced = remote.commit(branch_name="main", files={"data.txt": "trunk v2\n"})
        # An occupied commit worktree directory makes the trunk fail after its worktree moved.
        (repo.directory_commits / advanced).mkdir()
        (repo.directory_commits / advanced / "blocker.txt").write_text("blocking worktree creation\n")
        branches = await client.branch.all()

        @flow(name="test-sync-a-repository-whose-trunk-fails")
        async def _run_sync() -> None:
            await sync_repository_from_origin(
                repository=node,
                repo=repo,
                staging_branch=None,
                infrahub_branch=registry.default_branch,
                default_branch_id=branches[registry.default_branch].id,
                client=client,
            )

        await _run_sync()

        # The reason is the stderr of git, which names a temporary path.
        prefix = f"Unable to synchronize the default branch main of repository {name} at step collection: "
        default_branch_messages = [
            (record.levelno, record.getMessage().startswith(prefix))
            for record in caplog.records
            if record.name == FLOW_RUN_LOGGER and record.getMessage().startswith("Unable to synchronize the default")
        ]
        assert default_branch_messages == [(logging.ERROR, True)]
        recorded = await NodeManager.get_one(
            db=db, id=node.id, kind=CoreRepositoryNode, branch=registry.default_branch, raise_on_error=True
        )
        assert recorded.sync_status.value == RepositorySyncStatus.ERROR_IMPORT.value
