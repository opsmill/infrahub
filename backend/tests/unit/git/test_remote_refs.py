from __future__ import annotations

import asyncio
import os
import re
import time
from typing import TYPE_CHECKING

import pytest
from git import Repo

from infrahub.exceptions import RepositoryConnectionError, RepositoryError, RepositoryInvalidBranchError
from infrahub.git.remote_refs import RemoteRefs, ensure_branch_exists, list_remote_heads, list_remote_refs
from tests.helpers.git import install_remote_helper

if TYPE_CHECKING:
    from collections.abc import Callable
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


async def test_list_remote_heads_reads_only_the_branches_named_exactly(tmp_path: Path) -> None:
    """Git also lists a ref whose name ends with the requested one, such as team/refs/heads/feature."""
    source_dir = tmp_path / "source-repo"
    source = _init_source(source_dir, initial_branch="production")
    source.git.branch("feature")
    source.git.branch("team/refs/heads/feature")
    head = source.head.commit.hexsha

    heads = await list_remote_heads(
        name="demo", url=f"file://{source_dir}", branch_names=["feature", "missing"], timeout_seconds=30
    )

    assert heads == {"feature": head}


@pytest.mark.timeout(60)
async def test_list_remote_heads_stops_a_remote_that_does_not_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The remote helper git starts keeps the pipes open after git stops, so it has to stop too."""
    url = install_remote_helper(tmp_path, monkeypatch, script="exec sleep 600")

    with pytest.raises(
        RepositoryConnectionError, match=r"^The remote of repository demo did not answer within 2 seconds\.$"
    ):
        await list_remote_heads(name="demo", url=url, branch_names=["main"], timeout_seconds=2)


def wait_until(condition: Callable[[], bool], deadline_seconds: float = 20) -> bool:
    """Return whether the condition held before the deadline."""
    deadline = time.monotonic() + deadline_seconds
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.timeout(60)
async def test_list_remote_heads_stops_the_remote_when_the_read_is_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = tmp_path / "helper.pid"
    url = install_remote_helper(
        tmp_path, monkeypatch, script=f"echo $$ > {pid_file}.tmp\nmv {pid_file}.tmp {pid_file}\nexec sleep 60"
    )
    read = asyncio.create_task(list_remote_heads(name="demo", url=url, branch_names=["main"], timeout_seconds=50))
    assert await asyncio.to_thread(wait_until, pid_file.exists)
    helper_pid = int(pid_file.read_text(encoding="utf-8"))

    read.cancel()
    with pytest.raises(asyncio.CancelledError):
        await read

    assert await asyncio.to_thread(wait_until, lambda: not process_exists(helper_pid))


async def test_list_remote_heads_reads_git_in_english(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper echoes the locale git gives it, through an error git reports."""
    url = install_remote_helper(tmp_path, monkeypatch, script='echo "locale $LANGUAGE $LC_ALL" >&2\nexit 1')
    monkeypatch.setenv("LANGUAGE", "fr")
    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")

    with pytest.raises(RepositoryError, match=r"locale C C"):
        await list_remote_heads(name="demo", url=url, branch_names=["main"], timeout_seconds=30)


async def test_list_remote_heads_reports_text_that_is_not_utf8_as_a_repository_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = install_remote_helper(tmp_path, monkeypatch, script="printf 'broken \\377\\376 text\\n' >&2\nexit 1")

    with pytest.raises(RepositoryError, match=r"broken \ufffd\ufffd text"):
        await list_remote_heads(name="demo", url=url, branch_names=["main"], timeout_seconds=30)


async def test_list_remote_heads_reports_a_location_git_cannot_take_as_a_repository_error() -> None:
    """A location with a NUL byte cannot reach git at all, and the merge check must still read it as unreadable."""
    with pytest.raises(RepositoryError, match=r"^Unable to run git to read the remote of repository demo: "):
        await list_remote_heads(name="demo", url="file:///no\x00where", branch_names=["main"], timeout_seconds=30)


async def test_list_remote_heads_reports_a_git_that_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(RepositoryError, match=r"^Unable to run git to read the remote of repository demo: "):
        await list_remote_heads(name="demo", url="file:///nowhere", branch_names=["main"], timeout_seconds=30)


def location_that_reads_as_an_option(directory: Path) -> tuple[str, Path]:
    """Return a location that git would read as an option running a script, and the file the script writes."""
    marker = directory / "upload-pack-ran"
    script = directory / "upload-pack.sh"
    script.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n", encoding="utf-8")
    script.chmod(0o755)
    return f"--upload-pack={script}", marker


def test_list_remote_refs_reads_a_location_that_looks_like_an_option_as_a_location(tmp_path: Path) -> None:
    location, marker = location_that_reads_as_an_option(directory=tmp_path)

    with pytest.raises(RepositoryError, match=re.escape(location)):
        list_remote_refs(name="demo", url=location)

    assert not marker.exists()


async def test_list_remote_heads_reads_a_location_that_looks_like_an_option_as_a_location(tmp_path: Path) -> None:
    location, marker = location_that_reads_as_an_option(directory=tmp_path)

    with pytest.raises(RepositoryError, match=re.escape(location)):
        await list_remote_heads(name="demo", url=location, branch_names=["main"], timeout_seconds=30)

    assert not marker.exists()
