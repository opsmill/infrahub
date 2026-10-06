"""How a worker brings its own clone onto the commits another worker's fetch message pins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.git.convergence import WorktreeConverger
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus import Meta
from infrahub.message_bus.messages.refresh_git_fetch import BranchCommitPair, RefreshGitFetch
from tests.helpers.git import LocalRemote, clone_repository
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from infrahub.git.repository import InfrahubRepository

DELETED = "deleted-on-remote"


class StaticRepositoryLoader:
    def __init__(self, repository: InfrahubRepository) -> None:
        self.repository = repository

    async def load(self, message: RefreshGitFetch) -> InfrahubRepository:
        return self.repository


async def test_a_worker_that_converges_a_branch_it_lacks_writes_nothing_to_the_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A branch deleted on the remote after the synchronization must not come back from a converging worker."""
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()
    monkeypatch.setattr(registry, "_default_branch", "main")
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(repos_dir))
    remote = LocalRemote.create(directory=tmp_path / "remote", trunk="main", branches=[])
    pinned = remote.commit(branch_name=DELETED, files={"data.txt": "deleted branch\n"})
    repository = await clone_repository(
        id=UUIDT.new(),
        name="converging-repo",
        location=str(remote.directory),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        update_commit_value=False,
    )
    remote.delete_branch(DELETED)
    trunk = BranchCommitPair(
        infrahub_branch_name="main", infrahub_branch_id="main-id", commit=remote.repo.commit("main").hexsha
    )
    message = RefreshGitFetch(
        meta=Meta(initiator_id="syncing-worker"),
        location=str(remote.directory),
        repository_id=str(repository.id),
        repository_name=repository.name,
        repository_kind=InfrahubKind.REPOSITORY,
        infrahub_branch_name=trunk.infrahub_branch_name,
        infrahub_branch_id=trunk.infrahub_branch_id,
        commit=trunk.commit,
        branches=(
            trunk,
            BranchCommitPair(infrahub_branch_name=DELETED, infrahub_branch_id=f"{DELETED}-id", commit=pinned),
        ),
    )
    converger = WorktreeConverger(
        lock_registry=InfrahubLockRegistry(local_only=True),
        loader=StaticRepositoryLoader(repository=repository),
        worker_identity="converging-worker",
    )

    await converger.converge(message)

    assert [head.name for head in remote.repo.heads] == ["main"]
    assert repository.get_commit_value(branch_name=DELETED, remote=False) == pinned
