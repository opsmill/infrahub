import os
from collections.abc import Generator
from pathlib import Path

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.test_client import dummy_async_request


@pytest.fixture
def git_identity() -> Generator[None, None, None]:
    """Ensure git author/committer identity is set for environments without global git config (e.g. CI)."""
    env_vars = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
    original = {var: os.environ.get(var) for var in env_vars}

    os.environ["GIT_AUTHOR_NAME"] = "Test"
    os.environ["GIT_AUTHOR_EMAIL"] = "test@test.com"
    os.environ["GIT_COMMITTER_NAME"] = "Test"
    os.environ["GIT_COMMITTER_EMAIL"] = "test@test.com"

    yield

    for var, value in original.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value


@pytest.fixture
def git_repo_environment(tmp_path: Path) -> Generator[Path, None, None]:
    """Set up repositories directory and default branch for git tests."""
    old_default_branch = getattr(registry, "_default_branch", None)
    old_repos_dir = config.SETTINGS.git.repositories_directory

    registry._default_branch = "main"

    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    config.SETTINGS.git.repositories_directory = str(repos_dir)

    yield tmp_path

    config.SETTINGS.git.repositories_directory = old_repos_dir
    if old_default_branch is not None:
        registry._default_branch = old_default_branch


async def test_has_conflicting_changes_no_false_positive(
    git_identity: None,
    git_repo_environment: Path,
) -> None:
    """has_conflicting_changes() should not report false positives when
    file content contains conflict marker characters like '======='."""
    sources_dir = git_repo_environment / "source"
    sources_dir.mkdir()

    test_repo = MultipleStagesFileRepo(name="false-positive-conflicts", sources_directory=sources_dir)
    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=test_repo.name,
        location=test_repo.path,
        default_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # The branch adds a file containing ======= but has no actual conflicts with main
    assert not repository.has_conflicting_changes(target_branch="main", source_branch="change1")
