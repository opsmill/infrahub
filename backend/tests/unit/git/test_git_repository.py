from pathlib import Path

import pytest
from git import Repo
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.test_client import dummy_async_request


async def test_has_conflicting_changes_no_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """has_conflicting_changes() should not report false positives when
    file content contains conflict marker characters like '======='.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    sources_dir = tmp_path / "source"
    sources_dir.mkdir()

    test_repo = MultipleStagesFileRepo(name="false-positive-conflicts", sources_directory=sources_dir)
    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=test_repo.name,
        location=test_repo.path,
        default_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # Confirm the diff between the branches actually contains ======= to validate the test premise
    diff = test_repo.repo.git.diff("main", "change1")
    assert "=======" in diff

    # The branch adds a file containing ======= but has no actual conflicts with main
    assert not repository.has_conflicting_changes(target_branch="main", source_branch="change1")


def test_check_connectivity_ignores_cwd_git_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git operations must not be affected by a broken .git worktree pointer in the process current working directory."""
    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    Repo.init(source_dir, initial_branch="main")

    # Simulate a worktree environment: current working directory has a .git file pointing to a path that doesn't exist
    cwd = tmp_path / "broken-worktree"
    cwd.mkdir()
    (cwd / ".git").write_text("gitdir: /nonexistent/.git/worktrees/fake\n")
    monkeypatch.chdir(cwd)

    InfrahubRepository.check_connectivity(name="test", url=f"file://{source_dir}")
