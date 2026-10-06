"""How a worker brings its own clone onto the commits another worker's fetch message pins."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.git.convergence import WorktreeConverger
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus import Meta
from infrahub.message_bus.messages.refresh_git_fetch import BranchCommitPair, RefreshGitFetch
from tests.adapters.lock import LockTimeline, RecordingLockRegistry
from tests.helpers.git import LocalRemote, clone_repository
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.git.repository import InfrahubRepository

TASK_LOGGER = "infrahub.tasks"
"""The logger the worker sends to the flow run."""
REPOSITORY_NAME = "fanout-repo"
REPOSITORY_LOCK = f"repository.{REPOSITORY_NAME}"
THIS_WORKER = "this-worker"

TRUNK = BranchCommitPair(infrahub_branch_name="main", infrahub_branch_id="main-id", commit="a" * 40)
FEATURE = BranchCommitPair(infrahub_branch_name="feature", infrahub_branch_id="feature-id", commit="b" * 40)
REWRITTEN = BranchCommitPair(infrahub_branch_name="rewritten", infrahub_branch_id="rewritten-id", commit="c" * 40)
TRUNK_TO_PULL = BranchCommitPair(infrahub_branch_name="main", infrahub_branch_id="main-id", commit=None)


@dataclass(frozen=True)
class GitCall:
    operation: str
    branch_name: str | None = None
    commit: str | None = None
    branch_id: str | None = None
    create_if_missing: bool | None = None
    update_commit_value: bool | None = None
    lock_held: bool = False


@dataclass
class RecordingRepository:
    """Records each git operation and whether the repository lock was held when it ran."""

    timeline: LockTimeline
    failing_branches: frozenset[str] = frozenset()
    calls: list[GitCall] = field(default_factory=list)

    def _lock_held(self) -> bool:
        return REPOSITORY_LOCK in self.timeline.currently_held()

    async def fetch(self) -> bool:
        self.calls.append(GitCall(operation="fetch", lock_held=self._lock_held()))
        return True

    async def reset_to_commit(
        self,
        branch_name: str,
        commit: str,
        branch_id: str | None = None,
        create_if_missing: bool = False,
        update_commit_value: bool = True,
    ) -> None:
        self.calls.append(
            GitCall(
                operation="reset",
                branch_name=branch_name,
                commit=commit,
                branch_id=branch_id,
                create_if_missing=create_if_missing,
                update_commit_value=update_commit_value,
                lock_held=self._lock_held(),
            )
        )
        if branch_name in self.failing_branches:
            raise RepositoryError(identifier=REPOSITORY_NAME, message=f"Commit not found in the local clone: {commit}")

    async def pull(
        self,
        branch_name: str,
        branch_id: str | None = None,
        create_if_missing: bool = False,
        update_commit_value: bool = True,
    ) -> bool | str:
        self.calls.append(
            GitCall(
                operation="pull",
                branch_name=branch_name,
                branch_id=branch_id,
                create_if_missing=create_if_missing,
                update_commit_value=update_commit_value,
                lock_held=self._lock_held(),
            )
        )
        return True


@dataclass
class RecordingLoader:
    repository: RecordingRepository
    loaded: list[RefreshGitFetch] = field(default_factory=list)

    async def load(self, message: RefreshGitFetch) -> RecordingRepository:
        self.loaded.append(message)
        return self.repository


def build_message(
    branches: tuple[BranchCommitPair, ...] | None, commit: str | None, initiator_id: str | None = "other-worker"
) -> RefreshGitFetch:
    return RefreshGitFetch(
        meta=Meta(initiator_id=initiator_id),
        location="https://git.example.com/fanout-repo.git",
        repository_id="repository-id",
        repository_name=REPOSITORY_NAME,
        repository_kind="CoreRepository",
        infrahub_branch_name=TRUNK.infrahub_branch_name,
        infrahub_branch_id=TRUNK.infrahub_branch_id,
        commit=commit,
        branches=branches,
    )


def converged_reset(branch: BranchCommitPair) -> GitCall:
    return GitCall(
        operation="reset",
        branch_name=branch.infrahub_branch_name,
        commit=branch.commit,
        branch_id=branch.infrahub_branch_id,
        create_if_missing=True,
        update_commit_value=False,
        lock_held=True,
    )


FETCH = GitCall(operation="fetch", lock_held=True)
TRUNK_PULL = GitCall(
    operation="pull",
    branch_name="main",
    branch_id="main-id",
    create_if_missing=True,
    update_commit_value=False,
    lock_held=True,
)


@dataclass
class FanOutCase:
    name: str
    branches: tuple[BranchCommitPair, ...] | None
    commit: str | None
    expected_calls: list[GitCall]


FAN_OUT_CASES = [
    FanOutCase(
        name="every_listed_branch_is_reset",
        branches=(TRUNK, FEATURE, REWRITTEN),
        commit=TRUNK.commit,
        expected_calls=[FETCH, converged_reset(TRUNK), converged_reset(FEATURE), converged_reset(REWRITTEN)],
    ),
    FanOutCase(
        name="a_listed_branch_without_a_commit_is_pulled",
        branches=(TRUNK_TO_PULL, FEATURE),
        commit=None,
        expected_calls=[FETCH, TRUNK_PULL, converged_reset(FEATURE)],
    ),
    FanOutCase(
        name="without_a_list_the_pinned_branch_is_reset",
        branches=None,
        commit=TRUNK.commit,
        expected_calls=[FETCH, converged_reset(TRUNK)],
    ),
    FanOutCase(
        name="without_a_list_or_a_commit_the_branch_is_pulled",
        branches=None,
        commit=None,
        expected_calls=[FETCH, TRUNK_PULL],
    ),
]


@pytest.mark.parametrize("case", FAN_OUT_CASES, ids=[case.name for case in FAN_OUT_CASES])
async def test_branches_converge_under_one_lock_hold_and_one_fetch(case: FanOutCase) -> None:
    timeline = LockTimeline()
    repository = RecordingRepository(timeline=timeline)
    converger = WorktreeConverger(
        lock_registry=RecordingLockRegistry(timeline=timeline),
        loader=RecordingLoader(repository=repository),
        worker_identity=THIS_WORKER,
    )

    await converger.converge(build_message(branches=case.branches, commit=case.commit))

    assert repository.calls == case.expected_calls
    assert timeline.acquire_sequence() == [REPOSITORY_LOCK]
    assert timeline.currently_held() == set()


async def test_a_branch_that_cannot_be_reset_does_not_stop_the_others(caplog: pytest.LogCaptureFixture) -> None:
    timeline = LockTimeline()
    repository = RecordingRepository(timeline=timeline, failing_branches=frozenset({FEATURE.infrahub_branch_name}))
    converger = WorktreeConverger(
        lock_registry=RecordingLockRegistry(timeline=timeline),
        loader=RecordingLoader(repository=repository),
        worker_identity=THIS_WORKER,
    )

    caplog.set_level(logging.ERROR, logger=TASK_LOGGER)

    await converger.converge(build_message(branches=(TRUNK, FEATURE, REWRITTEN), commit=TRUNK.commit))

    assert repository.calls == [FETCH, converged_reset(TRUNK), converged_reset(FEATURE), converged_reset(REWRITTEN)]
    assert [
        (record.levelno, record.getMessage(), vars(record)["branch"])
        for record in caplog.records
        if record.name == TASK_LOGGER
    ] == [
        (
            logging.ERROR,
            f"Unable to converge branch feature of repository {REPOSITORY_NAME} on commit {FEATURE.commit}",
            "feature",
        )
    ]


async def test_a_message_this_worker_sent_is_ignored() -> None:
    timeline = LockTimeline()
    repository = RecordingRepository(timeline=timeline)
    loader = RecordingLoader(repository=repository)
    converger = WorktreeConverger(
        lock_registry=RecordingLockRegistry(timeline=timeline), loader=loader, worker_identity=THIS_WORKER
    )

    await converger.converge(build_message(branches=(TRUNK, FEATURE), commit=TRUNK.commit, initiator_id=THIS_WORKER))

    assert loader.loaded == []
    assert repository.calls == []
    assert timeline.acquire_sequence() == []


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
