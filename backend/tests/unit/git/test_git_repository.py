import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from git import Repo
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.test_client import dummy_async_request

PREFECT_LOGGER_NAME = "infrahub.git.base"


@pytest.fixture
def patch_prefect_logger() -> Any:
    """Replace Prefect's `get_run_logger` with a stdlib logger so calls outside a flow context succeed."""
    with patch(
        "infrahub.git.base.get_run_logger",
        return_value=logging.getLogger(PREFECT_LOGGER_NAME),
    ):
        yield


def _build_source_with_conflicting_branches(source_dir: Path) -> Repo:
    """Initialize a git source repo with `main` and `change1` whose tips edit the same lines."""
    source = Repo.init(source_dir, initial_branch="main")
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    target = source_dir / "data.txt"
    target.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    base_commit = source.index.commit("base")

    source.git.checkout("-b", "change1")
    target.write_text("change1 version\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("change on change1")

    source.git.checkout("main")
    source.git.reset("--hard", base_commit.hexsha)
    target.write_text("main version\nline 2\nline 3\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("change on main")
    return source


async def test_create_branch_in_git_with_conflicting_remote_lands_at_remote_tip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A remote branch that conflicts with the default branch must still be imported locally.

    The local branch should land at the remote tip so that downstream merge attempts can
    surface the conflict at merge time, rather than aborting the entire import.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    _build_source_with_conflicting_branches(source_dir)

    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="conflicting-import",
        location=str(source_dir),
        default_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    # Pre-condition: the two branches must actually conflict for this test to be meaningful
    assert repository.has_conflicting_changes(target_branch="main", source_branch="change1")

    remote_branches = repository.get_branches_from_remote()
    expected_commit = remote_branches["change1"].commit

    await repository.create_branch_in_git(branch_name="change1", branch_id=str(UUIDT.new()))

    local_branches = repository.get_branches_from_local(include_worktree=False)
    assert "change1" in local_branches
    assert local_branches["change1"].commit == expected_commit


async def test_validate_remote_branch_allows_conflicting_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch_prefect_logger: Any,
) -> None:
    """validate_remote_branch must accept a branch that conflicts with the default branch.

    Skipping the branch would prevent it from being imported. The conflict is surfaced at
    merge time instead.
    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))

    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()
    _build_source_with_conflicting_branches(source_dir)

    repository = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="conflicting-validate",
        location=str(source_dir),
        default_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    assert repository.has_conflicting_changes(target_branch="main", source_branch="change1")
    assert repository.validate_remote_branch(branch_name="change1") is True


async def test_has_conflicting_changes_no_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """has_conflicting_changes() should not report false positives when.

    file content contains conflict marker characters like '======='.

    """
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
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
