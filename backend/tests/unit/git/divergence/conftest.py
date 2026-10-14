from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from git import Repo

from infrahub.git.divergence.gateway import GitAncestryGateway

IMPORTED = "a" * 40
REMOTE = "b" * 40
ABSENT = "0" * 40


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo.init(tmp_path / "repository")


@pytest.fixture
def gateway(repo: Repo) -> GitAncestryGateway:
    return GitAncestryGateway(repository_name="test-repository", repo=repo)


def commit_file(repo: Repo, content: str) -> str:
    working_tree = repo.working_tree_dir
    assert working_tree is not None
    Path(working_tree, "file.txt").write_text(content, encoding="utf-8")
    repo.index.add(["file.txt"])
    return str(repo.index.commit(f"commit {content}").hexsha)


def break_object_database(repo: Repo) -> None:
    """Leave git unable to answer anything about this repository."""
    shutil.rmtree(Path(str(repo.git_dir), "objects"))


def pack_objects(repo: Repo) -> None:
    repo.git.gc("--prune=now")


def pack_directory_of(repo: Repo) -> Path:
    return Path(str(repo.git_dir), "objects", "pack")


def pack_loose_objects(repo: Repo) -> list[Path]:
    """Move the loose objects into a pack of their own, and return the files of that pack."""
    before = set(pack_directory_of(repo=repo).glob("pack-*"))
    repo.git.repack("-d")
    return sorted(set(pack_directory_of(repo=repo).glob("pack-*")) - before)


def deny_access_to_packs(repo: Repo) -> list[Path]:
    """Leave the packed objects present but unreadable, and return what to restore."""
    pack_directory = pack_directory_of(repo=repo)
    packs = sorted(pack_directory.glob("*.pack")) + sorted(pack_directory.glob("*.idx"))
    for pack in packs:
        pack.chmod(0o000)
    return packs
