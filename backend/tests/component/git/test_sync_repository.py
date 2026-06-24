from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from git import Repo
from infrahub_sdk import Config, InfrahubClient
from prefect import flow

from infrahub import config
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase
from infrahub.git import InfrahubRepository
from infrahub.git.tasks import sync_repository_from_origin
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.workers.dependencies import clear_singletons
from tests.adapters.message_bus import BusRecorder
from tests.conftest import TestHelper
from tests.helpers.test_client import dummy_async_request


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

    repo = await InfrahubRepository.new(
        id=node.id,
        name="test-repository",
        location=str(source_dir),
        default_branch_name=git_default_branch,
        internal_status=internal_status,
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
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
    """The commit broadcast to the worker pool resolves to the repository's git default branch HEAD.

    Holds across matching and mismatched default branches and staging syncs, so every worker
    converges on the same pinned commit.
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
            active_internal_status=scenario.active_internal_status,
            staging_branch=scenario.staging_branch,
            infrahub_branch=infrahub_branch,
            infrahub_branch_id="branch-id",
            client=client,
        )

    await _run_sync()

    fetch_messages = [message for message in message_bus_recorder.messages if isinstance(message, RefreshGitFetch)]
    assert len(fetch_messages) == 1

    expected_commit = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
    assert fetch_messages[0].commit == expected_commit
