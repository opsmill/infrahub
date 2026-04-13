from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import FileRepo
from tests.helpers.test_client import dummy_async_request


@pytest.fixture
def git_sources_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    return source_dir


@pytest.fixture
def git_repos_dir(tmp_path: Path) -> Path:
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    config.SETTINGS.git.repositories_directory = str(repos_dir)
    return repos_dir


@pytest.fixture
def setup_registry() -> None:
    registry._default_branch = "main"


@pytest.fixture
def upstream_repo(git_sources_dir: Path) -> FileRepo:
    return FileRepo(name="car-dealership", sources_directory=git_sources_dir)


@pytest.fixture
async def infrahub_repo(
    upstream_repo: FileRepo,
    git_repos_dir: Path,
    setup_registry: None,
) -> InfrahubRepository:
    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="car-dealership",
        location=upstream_repo.path,
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    return repo


async def test_sync_detects_stale_db_commit(infrahub_repo: InfrahubRepository) -> None:
    """When db_commits has a different commit than local HEAD, sync calls
    update_commit_value and import_objects_from_files for the stale branch."""

    # Get the real local commit for the default branch
    local_commit = infrahub_repo.get_commit_value(branch_name="main", remote=False)
    stale_db_commit = "0000000000000000000000000000000000000000"

    assert local_commit != stale_db_commit

    # Ensure the repo is ACTIVE so the processing block runs
    infrahub_repo.internal_status = RepositoryInternalStatus.ACTIVE.value

    mock_fetch = AsyncMock()
    mock_compare = AsyncMock(return_value=([], []))
    mock_update_commit = AsyncMock()
    mock_import = AsyncMock()

    with (
        patch.object(InfrahubRepository, "fetch", mock_fetch),
        patch.object(InfrahubRepository, "compare_local_remote", mock_compare),
        patch.object(InfrahubRepository, "update_commit_value", mock_update_commit),
        patch.object(InfrahubRepository, "import_objects_from_files", mock_import),
    ):
        await infrahub_repo.sync(db_commits={"main": stale_db_commit})

        mock_fetch.assert_awaited_once()
        mock_compare.assert_awaited_once()
        mock_update_commit.assert_awaited_once_with(branch_name="main", commit=local_commit)
        mock_import.assert_awaited_once_with(infrahub_branch_name="main", commit=local_commit)


async def test_sync_skips_when_db_commit_matches(infrahub_repo: InfrahubRepository) -> None:
    """When db_commits matches local HEAD, no import is triggered."""

    local_commit = infrahub_repo.get_commit_value(branch_name="main", remote=False)

    infrahub_repo.internal_status = RepositoryInternalStatus.ACTIVE.value

    mock_fetch = AsyncMock()
    mock_compare = AsyncMock(return_value=([], []))
    mock_update_commit = AsyncMock()
    mock_import = AsyncMock()

    with (
        patch.object(InfrahubRepository, "fetch", mock_fetch),
        patch.object(InfrahubRepository, "compare_local_remote", mock_compare),
        patch.object(InfrahubRepository, "update_commit_value", mock_update_commit),
        patch.object(InfrahubRepository, "import_objects_from_files", mock_import),
    ):
        await infrahub_repo.sync(db_commits={"main": local_commit})

        mock_fetch.assert_awaited_once()
        mock_compare.assert_awaited_once()
        mock_update_commit.assert_not_awaited()
        mock_import.assert_not_awaited()


async def test_sync_without_db_commits_preserves_existing_behavior(infrahub_repo: InfrahubRepository) -> None:
    """When db_commits is None (not provided), no stale detection occurs and
    the method returns early when compare_local_remote finds nothing."""

    infrahub_repo.internal_status = RepositoryInternalStatus.ACTIVE.value

    mock_fetch = AsyncMock()
    mock_compare = AsyncMock(return_value=([], []))
    mock_update_commit = AsyncMock()
    mock_import = AsyncMock()

    with (
        patch.object(InfrahubRepository, "fetch", mock_fetch),
        patch.object(InfrahubRepository, "compare_local_remote", mock_compare),
        patch.object(InfrahubRepository, "update_commit_value", mock_update_commit),
        patch.object(InfrahubRepository, "import_objects_from_files", mock_import),
    ):
        await infrahub_repo.sync()

        mock_fetch.assert_awaited_once()
        mock_compare.assert_awaited_once()
        mock_update_commit.assert_not_awaited()
        mock_import.assert_not_awaited()
