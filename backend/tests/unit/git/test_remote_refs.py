from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from git import Repo

from infrahub.exceptions import RepositoryConnectionError, RepositoryInvalidBranchError
from infrahub.git.remote_refs import RemoteRefs, ensure_branch_exists, list_remote_refs

if TYPE_CHECKING:
    from pathlib import Path


def _init_source(directory: Path, initial_branch: str) -> Repo:
    directory.mkdir(parents=True, exist_ok=True)
    source = Repo.init(directory, initial_branch=initial_branch)
    with source.config_writer() as cfg:
        cfg.set_value("user", "name", "Test")
        cfg.set_value("user", "email", "test@test.local")
    (directory / "data.txt").write_text("content\n", encoding="utf-8")
    source.index.add(["data.txt"])
    source.index.commit("initial")
    return source


def test_list_remote_refs_reads_default_branch_and_branches(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-repo"
    source = _init_source(source_dir, initial_branch="production")
    source.git.branch("feature")

    refs = list_remote_refs(name="demo", url=f"file://{source_dir}")

    assert refs == RemoteRefs(default_branch="production", branches=frozenset({"production", "feature"}))


def test_list_remote_refs_on_empty_remote(tmp_path: Path) -> None:
    source_dir = tmp_path / "empty-repo.git"
    source_dir.mkdir()
    Repo.init(source_dir, bare=True, initial_branch="main")

    refs = list_remote_refs(name="demo", url=f"file://{source_dir}")

    assert refs == RemoteRefs(default_branch=None, branches=frozenset())


def test_list_remote_refs_with_detached_head(tmp_path: Path) -> None:
    source_dir = tmp_path / "detached-repo"
    source = _init_source(source_dir, initial_branch="production")
    source.git.branch("feature")
    source.git.checkout(source.head.commit.hexsha)

    refs = list_remote_refs(name="demo", url=f"file://{source_dir}")

    assert refs == RemoteRefs(default_branch=None, branches=frozenset({"production", "feature"}))


def test_list_remote_refs_ignores_cwd_git_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git operations must not be affected by a broken .git worktree pointer in the process current working directory."""
    source_dir = tmp_path / "source-repo"
    _init_source(source_dir, initial_branch="main")

    cwd = tmp_path / "broken-worktree"
    cwd.mkdir()
    (cwd / ".git").write_text("gitdir: /nonexistent/.git/worktrees/fake\n")
    monkeypatch.chdir(cwd)

    refs = list_remote_refs(name="demo", url=f"file://{source_dir}")

    assert refs == RemoteRefs(default_branch="main", branches=frozenset({"main"}))


def test_list_remote_refs_classifies_an_unreachable_remote(tmp_path: Path) -> None:
    with pytest.raises(
        RepositoryConnectionError,
        match=r"^Unable to clone the repository demo, please check the address and the credential$",
    ):
        list_remote_refs(name="demo", url=f"file://{tmp_path}/nonexistent.git")


def test_ensure_branch_exists_accepts_a_branch_that_is_not_the_remote_default() -> None:
    refs = RemoteRefs(default_branch="stable", branches=frozenset({"stable", "main"}))

    ensure_branch_exists(refs, branch_name="main", repository_name="demo", location="https://example.com/demo.git")


def test_ensure_branch_exists_names_the_remote_default_branch() -> None:
    refs = RemoteRefs(default_branch="stable", branches=frozenset({"stable"}))

    with pytest.raises(
        RepositoryInvalidBranchError,
        match=r"^Branch 'main' does not exist on the remote repository demo; the remote's default branch is 'stable'\.$",
    ):
        ensure_branch_exists(refs, branch_name="main", repository_name="demo", location="https://example.com/demo.git")


def test_ensure_branch_exists_reports_a_remote_without_a_default_branch() -> None:
    refs = RemoteRefs(default_branch=None, branches=frozenset())

    with pytest.raises(
        RepositoryInvalidBranchError,
        match=r"^Branch 'main' does not exist on the remote repository demo; the remote is empty or has no default branch\.$",
    ):
        ensure_branch_exists(refs, branch_name="main", repository_name="demo", location="https://example.com/demo.git")


def test_ensure_branch_exists_does_not_name_a_default_branch_the_remote_hides() -> None:
    """A remote can advertise a default branch it withholds from the listing, which must not be recommended."""
    refs = RemoteRefs(default_branch="main", branches=frozenset({"dev"}))

    with pytest.raises(
        RepositoryInvalidBranchError,
        match=r"^Branch 'main' does not exist on the remote repository demo; the remote is empty or has no default branch\.$",
    ):
        ensure_branch_exists(refs, branch_name="main", repository_name="demo", location="https://example.com/demo.git")
