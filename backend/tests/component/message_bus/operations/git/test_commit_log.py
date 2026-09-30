from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from git import Actor, Repo
from git.exc import GitCommandError

from infrahub import config, lock
from infrahub.core.constants import (
    InfrahubKind,
    RepositoryCommitState,
    RepositoryGitCondition,
    RepositoryGitUnavailableReason,
)
from infrahub.exceptions import RepositoryError
from infrahub.git.models import GitRepositoryWarmUp
from infrahub.git.state.commit_log_wire import message_to_request
from infrahub.git.state.log_reader import RepositoryLogReader
from infrahub.git.state.models import CommitLogResult
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus.messages.git_commit_log_get import (
    GitCommitLogGet,
    GitCommitLogGetResponse,
    GitCommitLogGetResponseData,
)
from infrahub.message_bus.operations.git import commit_log
from infrahub.message_bus.types import KVTTL
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import build_cache, build_message_bus, build_workflow
from infrahub.workflows.catalogue import GIT_REPOSITORY_WARM_UP
from tests.adapters.cache import CacheSetCall, RecordingCache
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

    from fast_depends import Provider

    from infrahub.context import InfrahubContext
    from infrahub.events.models import EventContext
    from infrahub.git import InfrahubRepository
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo
    from tests.conftest import TestHelper

    ReadLog = Callable[[GitCommitLogGet], Awaitable[GitCommitLogGetResponseData]]
    SendLogRequest = Callable[[GitCommitLogGet], Awaitable[GitCommitLogGetResponse]]

AUTHOR = Actor("Ada Lovelace", "ada@example.com")
UNKNOWN_COMMIT = "deadbeef" * 5
PINNED_FETCH_TIME = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
NEVER_CLONED_NAME = "never-cloned"
NEVER_CLONED_LOCATION = "/tmp/never-cloned"
WARM_UP_STARTED = "The answering worker holds no local copy of this repository yet. A warm-up has been started."
WARM_UP_PENDING = "The answering worker holds no local copy of this repository yet. A warm-up is already in progress."


class UnreachableWorkflow(WorkflowRecorder):
    """Fails every submission, as a workflow engine that cannot be reached does."""

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        raise ConnectionError("workflow engine unreachable")


@pytest.fixture
def upstream(git_fixture_repo: InfrahubRepository, git_sources_dir: Path) -> Repo:
    return Repo(git_sources_dir / "test_base")


@pytest.fixture
def clone(git_fixture_repo: InfrahubRepository) -> Repo:
    return git_fixture_repo.get_git_repo_main()


@pytest.fixture
def recording_cache() -> RecordingCache:
    return RecordingCache()


@pytest.fixture
def workflow_recorder() -> WorkflowRecorder:
    return WorkflowRecorder()


@pytest.fixture
def local_lock_registry() -> Iterator[InfrahubLockRegistry]:
    """Install an in-process lock registry as the global one, so any lock the code under test takes is this one."""
    original = lock.registry
    lock.registry = InfrahubLockRegistry(local_only=True)
    yield lock.registry
    lock.registry = original


@pytest.fixture
async def repository_lock_held_by_an_import(
    git_fixture_repo: InfrahubRepository, local_lock_registry: InfrahubLockRegistry
) -> AsyncIterator[None]:
    """Hold the repository lock from another task, since the lock is re-entrant within the task holding it."""
    held = asyncio.Event()
    release = asyncio.Event()

    async def import_holding_the_lock() -> None:
        async with local_lock_registry.get(name=git_fixture_repo.name, namespace="repository"):
            held.set()
            await release.wait()

    holder = asyncio.create_task(import_holding_the_lock())
    await held.wait()
    yield
    release.set()
    await holder


@pytest.fixture
def log_reader(recording_cache: RecordingCache, workflow_recorder: WorkflowRecorder) -> RepositoryLogReader:
    return RepositoryLogReader(cache=recording_cache, workflow=workflow_recorder, worker_identity=WORKER_IDENTITY)


@pytest.fixture
def send_log_request(
    helper: TestHelper,
    dependency_provider: Provider,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> SendLogRequest:
    """Send a request through the message bus to the handler and return the reply, failed or not."""

    async def _send(message: GitCommitLogGet) -> GitCommitLogGetResponse:
        bus = await helper.get_message_bus_simulator()
        with (
            dependency_provider.scope(build_message_bus, lambda: bus),
            dependency_provider.scope(build_cache, lambda: recording_cache),
            dependency_provider.scope(build_workflow, lambda: workflow_recorder),
        ):
            return await bus.rpc(message=message, response_class=GitCommitLogGetResponse)

    return _send


@pytest.fixture
def read_log(send_log_request: SendLogRequest) -> ReadLog:
    """Send a request through the message bus to the handler and return the answer it replied with."""

    async def _read(message: GitCommitLogGet) -> GitCommitLogGetResponseData:
        reply = await send_log_request(message)
        assert reply.passed
        return reply.data

    return _read


def _commit(repo: Repo, name: str, day: int) -> str:
    """Commit one new file with a pinned author and date, and return its hash."""
    Path(repo.working_dir, f"{name}.txt").write_text(name, encoding="utf-8")
    repo.index.add([f"{name}.txt"])
    # Later than the fixture's own first commit, which is dated when the test runs, so walk order is fixed.
    date = f"2099-10-{day:02d}T12:00:00+0000"
    return repo.index.commit(
        f"Add {name}\n\nBody of {name}.", author=AUTHOR, committer=AUTHOR, author_date=date, commit_date=date
    ).hexsha


def _fetch(clone: Repo) -> None:
    clone.remotes.origin.fetch(prune=True, tags=True, prune_tags=True)


def _pin_fetch_time(clone: Repo, moment: datetime) -> None:
    timestamp = moment.timestamp()
    os.utime(Path(clone.git_dir) / "FETCH_HEAD", (timestamp, timestamp))


def _message(
    repository: InfrahubRepository,
    imported_commit: str | None,
    repository_kind: str = InfrahubKind.REPOSITORY,
    git_ref: str = "main",
    limit: int = 10,
    offset: int = 0,
    include_pending_count: bool = True,
) -> GitCommitLogGet:
    return GitCommitLogGet(
        repository_id=str(repository.id),
        repository_name=repository.name,
        repository_kind=repository_kind,
        location=repository.get_location(),
        infrahub_branch_name="main",
        git_ref=git_ref,
        imported_commit=imported_commit,
        limit=limit,
        offset=offset,
        include_pending_count=include_pending_count,
    )


def _never_cloned_message(repository_id: str, imported_commit: str | None) -> GitCommitLogGet:
    return GitCommitLogGet(
        repository_id=repository_id,
        repository_name=NEVER_CLONED_NAME,
        repository_kind=InfrahubKind.REPOSITORY,
        location=NEVER_CLONED_LOCATION,
        infrahub_branch_name="main",
        git_ref="main",
        imported_commit=imported_commit,
        limit=10,
        offset=0,
        include_pending_count=True,
    )


def _states(data: GitCommitLogGetResponseData) -> list[tuple[str, RepositoryCommitState]]:
    return [(commit.hash, commit.state) for commit in data.commits]


async def test_behind_reports_the_pending_range_and_every_state(
    git_fixture_repo: InfrahubRepository,
    upstream: Repo,
    clone: Repo,
    read_log: ReadLog,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    first = upstream.head.commit.hexsha
    imported = _commit(repo=upstream, name="imported", day=1)
    middle = _commit(repo=upstream, name="middle", day=2)
    head = _commit(repo=upstream, name="head", day=3)
    _fetch(clone=clone)

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=imported))

    assert data.condition is RepositoryGitCondition.BEHIND
    assert data.remote_head == head
    assert data.imported_commit == imported
    assert data.pending_count == 2
    assert data.unavailable_reason is None
    assert _states(data) == [
        (head, RepositoryCommitState.HEAD),
        (middle, RepositoryCommitState.PENDING),
        (imported, RepositoryCommitState.IMPORTED),
        (first, RepositoryCommitState.HISTORY),
    ]
    assert data.commits[0].model_dump() == {
        "hash": head,
        "message": "Add head\n\nBody of head.",
        "author_name": "Ada Lovelace",
        "authored_at": datetime(2099, 10, 3, 12, 0, tzinfo=UTC),
        "committed_at": datetime(2099, 10, 3, 12, 0, tzinfo=UTC),
        "state": RepositoryCommitState.HEAD,
    }
    assert recording_cache.set_calls == []
    assert workflow_recorder.calls == []


async def test_in_sync_puts_both_markers_on_one_commit(
    git_fixture_repo: InfrahubRepository, clone: Repo, read_log: ReadLog
) -> None:
    head = clone.commit("origin/main").hexsha

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=head))

    assert data.condition is RepositoryGitCondition.IN_SYNC
    assert data.remote_head == head
    assert data.imported_commit == head
    assert data.pending_count is None
    assert _states(data) == [(head, RepositoryCommitState.IMPORTED)]


async def test_a_force_pushed_ref_reads_as_rewritten(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, tmp_path: Path, read_log: ReadLog
) -> None:
    first = upstream.head.commit.hexsha
    imported = _commit(repo=upstream, name="imported", day=1)
    _fetch(clone=clone)

    pusher = Repo.clone_from(upstream.working_dir, tmp_path / "pusher")
    pusher.git.reset("--hard", first)
    rewritten_head = _commit(repo=pusher, name="rewritten", day=2)
    pusher.git.push("--force", "origin", "main")
    _fetch(clone=clone)

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=imported))

    assert data.condition is RepositoryGitCondition.REWRITTEN
    assert data.remote_head == rewritten_head
    assert data.imported_commit == imported
    assert data.pending_count is None
    assert _states(data) == [
        (rewritten_head, RepositoryCommitState.HEAD),
        (first, RepositoryCommitState.UNRELATED),
    ]


async def test_a_mapped_branch_with_no_commits_on_the_remote_reads_as_no_remote(
    git_fixture_repo: InfrahubRepository, clone: Repo, read_log: ReadLog
) -> None:
    head = clone.commit("origin/main").hexsha

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=head, git_ref="never-pushed"))

    assert data.condition is RepositoryGitCondition.NO_REMOTE
    assert data.remote_head is None
    assert data.imported_commit == head
    assert data.pending_count is None
    assert data.unavailable_reason is None
    assert data.commits == []


async def test_an_imported_commit_the_clone_does_not_hold_reads_as_orphaned(
    git_fixture_repo: InfrahubRepository, clone: Repo, read_log: ReadLog
) -> None:
    head = clone.commit("origin/main").hexsha

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=UNKNOWN_COMMIT))

    assert data.condition is RepositoryGitCondition.ORPHANED
    assert data.remote_head == head
    assert data.imported_commit is None
    assert data.pending_count is None
    assert data.error_message is None
    assert _states(data) == [(head, RepositoryCommitState.HEAD)]


async def test_paging_walks_a_known_history(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog
) -> None:
    first = upstream.head.commit.hexsha
    created = [_commit(repo=upstream, name=f"step{day}", day=day) for day in range(1, 6)]
    _fetch(clone=clone)
    newest_first = [*reversed(created), first]

    pages = [
        await read_log(_message(repository=git_fixture_repo, imported_commit=first, limit=2, offset=offset))
        for offset in (0, 2, 4, 6)
    ]

    assert [[commit.hash for commit in page.commits] for page in pages] == [
        newest_first[0:2],
        newest_first[2:4],
        newest_first[4:6],
        [],
    ]
    assert [page.pending_count for page in pages] == [5, 5, 5, 5]


async def test_fetched_at_follows_the_last_fetch(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog
) -> None:
    head = upstream.head.commit.hexsha
    _fetch(clone=clone)
    _pin_fetch_time(clone=clone, moment=PINNED_FETCH_TIME)
    message = _message(repository=git_fixture_repo, imported_commit=head)

    before = await read_log(message)
    _commit(repo=upstream, name="later", day=1)
    _fetch(clone=clone)
    after = await read_log(message)

    assert before.fetched_at == PINNED_FETCH_TIME
    assert after.fetched_at is not None
    assert after.fetched_at > PINNED_FETCH_TIME


async def test_a_clone_never_fetched_reports_no_fetch_time(
    git_fixture_repo: InfrahubRepository, clone: Repo, read_log: ReadLog
) -> None:
    Path(clone.git_dir, "FETCH_HEAD").unlink(missing_ok=True)

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=clone.commit("origin/main").hexsha))

    assert data.condition is RepositoryGitCondition.IN_SYNC
    assert data.fetched_at is None


async def test_an_unselected_pending_count_is_not_reported(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog
) -> None:
    imported = upstream.head.commit.hexsha
    _commit(repo=upstream, name="pending", day=1)
    _fetch(clone=clone)

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=imported, include_pending_count=False))

    assert data.condition is RepositoryGitCondition.BEHIND
    assert data.pending_count is None


async def test_a_read_only_branch_ref_reads_its_remote_branch(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog
) -> None:
    imported = upstream.head.commit.hexsha
    head = _commit(repo=upstream, name="advanced", day=1)
    _fetch(clone=clone)

    data = await read_log(
        _message(
            repository=git_fixture_repo,
            imported_commit=imported,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            git_ref="main",
        )
    )

    assert data.condition is RepositoryGitCondition.BEHIND
    assert data.remote_head == head
    assert _states(data) == [(head, RepositoryCommitState.HEAD), (imported, RepositoryCommitState.IMPORTED)]


@dataclass(frozen=True)
class PinnedCommitCase:
    name: str
    hash_length: int


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(PinnedCommitCase(name="full_hash", hash_length=40), id="full_hash"),
        pytest.param(PinnedCommitCase(name="abbreviated_hash", hash_length=12), id="abbreviated_hash"),
    ],
)
async def test_a_read_only_repository_pinned_to_a_commit_reads_that_commit(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog, case: PinnedCommitCase
) -> None:
    """A commit hash is a valid ref and names no branch or tag, so it must not read as a deleted ref."""
    pinned = upstream.head.commit.hexsha
    _commit(repo=upstream, name="after-pin", day=1)
    _fetch(clone=clone)

    data = await read_log(
        _message(
            repository=git_fixture_repo,
            imported_commit=pinned,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            git_ref=pinned[: case.hash_length],
        )
    )

    assert data.condition is RepositoryGitCondition.IN_SYNC
    assert data.remote_head == pinned
    assert _states(data) == [(pinned, RepositoryCommitState.IMPORTED)]


async def test_a_read_only_tag_ref_reads_the_tagged_commit(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog
) -> None:
    imported = upstream.head.commit.hexsha
    tagged = _commit(repo=upstream, name="release", day=1)
    upstream.create_tag("v1.0", ref=tagged, message="Release 1.0")
    _commit(repo=upstream, name="after-release", day=2)
    _fetch(clone=clone)

    data = await read_log(
        _message(
            repository=git_fixture_repo,
            imported_commit=imported,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            git_ref="v1.0",
        )
    )

    assert data.condition is RepositoryGitCondition.BEHIND
    assert data.remote_head == tagged
    assert data.pending_count == 1


async def test_a_read_only_ref_deleted_upstream_reads_as_missing_with_the_history_still_run(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog
) -> None:
    """The local branch the clone checked out survives the deletion and must not stand in for the remote."""
    first = upstream.head.commit.hexsha
    upstream.create_head("release", first)
    upstream.git.checkout("release")
    imported = _commit(repo=upstream, name="release", day=1)
    upstream.git.checkout("main")
    _fetch(clone=clone)
    clone.create_head("release", "origin/release")
    upstream.delete_head("release", force=True)
    _fetch(clone=clone)

    data = await read_log(
        _message(
            repository=git_fixture_repo,
            imported_commit=imported,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            git_ref="release",
        )
    )

    second_page = await read_log(
        _message(
            repository=git_fixture_repo,
            imported_commit=imported,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            git_ref="release",
            limit=1,
            offset=1,
        )
    )

    assert data.condition is RepositoryGitCondition.REF_MISSING
    assert data.remote_head is None
    assert data.imported_commit == imported
    assert data.pending_count is None
    assert data.unavailable_reason is None
    assert _states(data) == [(imported, RepositoryCommitState.IMPORTED), (first, RepositoryCommitState.HISTORY)]
    assert _states(second_page) == [(first, RepositoryCommitState.HISTORY)]


async def test_a_merged_side_branch_is_pending_below_the_imported_commit(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_log: ReadLog
) -> None:
    """A side branch forked before the import and merged after it lists its commit below the imported one."""
    first = upstream.head.commit.hexsha
    upstream.create_head("side", first)
    upstream.git.checkout("side")
    side = _commit(repo=upstream, name="side", day=1)
    upstream.git.checkout("main")
    imported = _commit(repo=upstream, name="imported", day=2)
    upstream.git.merge("side", "--no-ff", "-m", "Merge side")
    merge = upstream.head.commit.hexsha
    _fetch(clone=clone)

    data = await read_log(_message(repository=git_fixture_repo, imported_commit=imported))

    assert data.condition is RepositoryGitCondition.BEHIND
    assert data.pending_count == 2
    assert _states(data) == [
        (merge, RepositoryCommitState.HEAD),
        (imported, RepositoryCommitState.IMPORTED),
        (side, RepositoryCommitState.PENDING),
        (first, RepositoryCommitState.HISTORY),
    ]


async def test_a_git_failure_is_raised_without_its_output(
    git_fixture_repo: InfrahubRepository, clone: Repo, tmp_path: Path, log_reader: RepositoryLogReader
) -> None:
    """A head whose parent the clone does not hold makes the ancestry test fail rather than answer."""
    first = clone.commit("origin/main").hexsha
    broken_commit = tmp_path / "broken-commit"
    broken_commit.write_text(
        f"tree {clone.commit('origin/main').tree.hexsha}\nparent {UNKNOWN_COMMIT}\n"
        "author Ada Lovelace <ada@example.com> 1790000000 +0000\n"
        "committer Ada Lovelace <ada@example.com> 1790000000 +0000\n\nBroken parent\n",
        encoding="utf-8",
    )
    broken = clone.git.hash_object("-t", "commit", "-w", "--literally", str(broken_commit))
    clone.git.update_ref("refs/remotes/origin/main", broken)
    request = message_to_request(message=_message(repository=git_fixture_repo, imported_commit=first))

    with pytest.raises(
        RepositoryError, match=r"^Git failed while reading the commit log of test_basename\.$"
    ) as raised:
        await log_reader.commits(request=request)

    assert isinstance(raised.value.__cause__, GitCommandError)


async def test_a_failed_read_reaches_the_caller_as_a_failed_reply(
    git_fixture_repo: InfrahubRepository, clone: Repo, send_log_request: SendLogRequest
) -> None:
    shutil.rmtree(git_fixture_repo.directory_commits / clone.head.commit.hexsha)

    reply = await send_log_request(_message(repository=git_fixture_repo, imported_commit=None))

    assert reply.passed is False
    assert reply.errors == ["The directory for the main commit is missing for test_basename"]


async def test_a_request_without_a_reply_address_is_read_without_replying(
    git_fixture_repo: InfrahubRepository,
    clone: Repo,
    dependency_provider: Provider,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    """The bus double refuses any reply, so a handler that replied regardless would fail here."""
    bus = BusRecorder()
    message = _message(repository=git_fixture_repo, imported_commit=clone.commit("origin/main").hexsha)

    with (
        dependency_provider.scope(build_message_bus, lambda: bus),
        dependency_provider.scope(build_cache, lambda: recording_cache),
        dependency_provider.scope(build_workflow, lambda: workflow_recorder),
    ):
        await commit_log.get(message=message)

    assert bus.messages == []


async def test_an_unsupported_repository_kind_is_refused(
    git_fixture_repo: InfrahubRepository, log_reader: RepositoryLogReader
) -> None:
    message = _message(
        repository=git_fixture_repo, imported_commit=None, repository_kind=InfrahubKind.GENERICREPOSITORY
    )

    with pytest.raises(ValueError, match=r"^Reading a commit log is not supported for a CoreGenericRepository$"):
        await log_reader.commits(request=message_to_request(message=message))


async def test_a_broken_clone_raises_instead_of_reading_as_not_cloned(
    git_fixture_repo: InfrahubRepository,
    clone: Repo,
    log_reader: RepositoryLogReader,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    shutil.rmtree(git_fixture_repo.directory_commits / clone.head.commit.hexsha)
    message = _message(repository=git_fixture_repo, imported_commit=None)

    with pytest.raises(RepositoryError, match=r"^The directory for the main commit is missing for test_basename$"):
        await log_reader.commits(request=message_to_request(message=message))

    assert recording_cache.set_calls == []
    assert workflow_recorder.calls == []


async def test_a_read_during_a_clone_in_progress_reports_the_warm_up(
    git_fixture_repo: InfrahubRepository,
    clone: Repo,
    log_reader: RepositoryLogReader,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    """A copy still being cloned fails validation like a broken one, but a held claim says why."""
    shutil.rmtree(git_fixture_repo.directory_commits / clone.head.commit.hexsha)
    recording_cache.storage[f"git:warmup:{git_fixture_repo.id}"] = "another-worker"
    message = _message(repository=git_fixture_repo, imported_commit=None)

    result = await log_reader.commits(request=message_to_request(message=message))

    assert result == CommitLogResult(
        condition=RepositoryGitCondition.UNAVAILABLE,
        unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
        error_message=WARM_UP_PENDING,
    )
    assert recording_cache.set_calls == []
    assert workflow_recorder.calls == []


async def test_each_worker_answers_from_the_clone_it_holds(
    git_fixture_repo: InfrahubRepository,
    upstream: Repo,
    clone: Repo,
    git_repos_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    log_reader: RepositoryLogReader,
) -> None:
    """Two workers whose clones were last fetched at different times each report their own view."""
    stale_head = upstream.head.commit.hexsha
    _fetch(clone=clone)
    _pin_fetch_time(clone=clone, moment=PINNED_FETCH_TIME)

    fresh_repos_dir = tmp_path / "fresh-worker"
    shutil.copytree(git_repos_dir / str(git_fixture_repo.id), fresh_repos_dir / str(git_fixture_repo.id))
    fresh_clone = Repo(fresh_repos_dir / str(git_fixture_repo.id) / "main")
    fresh_head = _commit(repo=upstream, name="fresh", day=1)
    _fetch(clone=fresh_clone)
    fresh_fetch_time = datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)
    _pin_fetch_time(clone=fresh_clone, moment=fresh_fetch_time)
    request = message_to_request(message=_message(repository=git_fixture_repo, imported_commit=stale_head))

    stale = await log_reader.commits(request=request)
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(fresh_repos_dir))
    fresh = await log_reader.commits(request=request)

    assert (stale.condition, stale.remote_head, stale.fetched_at) == (
        RepositoryGitCondition.IN_SYNC,
        stale_head,
        PINNED_FETCH_TIME,
    )
    assert (fresh.condition, fresh.remote_head, fresh.fetched_at) == (
        RepositoryGitCondition.BEHIND,
        fresh_head,
        fresh_fetch_time,
    )


async def test_a_worker_without_a_clone_starts_a_warm_up(
    git_repos_dir: Path, read_log: ReadLog, recording_cache: RecordingCache, workflow_recorder: WorkflowRecorder
) -> None:
    repository_id = str(uuid.uuid4())

    data = await read_log(_never_cloned_message(repository_id=repository_id, imported_commit=UNKNOWN_COMMIT))

    assert data.condition is RepositoryGitCondition.UNAVAILABLE
    assert data.unavailable_reason is RepositoryGitUnavailableReason.NOT_CLONED
    assert data.error_message == WARM_UP_STARTED
    assert data.warm_up_task_id is not None
    assert str(uuid.UUID(data.warm_up_task_id)) == data.warm_up_task_id
    assert data.commits == []
    assert recording_cache.set_calls == [
        CacheSetCall(
            key=f"git:warmup:{repository_id}", value=WORKER_IDENTITY, expires=KVTTL.ONE_MINUTE, not_exists=True
        )
    ]
    assert workflow_recorder.submit_calls == [
        {
            "kind": "submit",
            "workflow": GIT_REPOSITORY_WARM_UP,
            "parameters": {
                "model": GitRepositoryWarmUp(
                    repository_id=repository_id,
                    repository_name=NEVER_CLONED_NAME,
                    repository_kind=InfrahubKind.REPOSITORY,
                    location=NEVER_CLONED_LOCATION,
                    infrahub_branch_name="main",
                )
            },
            "tags": [],
        }
    ]


async def test_concurrent_reads_without_a_clone_start_one_warm_up(
    git_repos_dir: Path,
    log_reader: RepositoryLogReader,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    request = message_to_request(
        message=_never_cloned_message(repository_id=str(uuid.uuid4()), imported_commit=UNKNOWN_COMMIT)
    )

    results = await asyncio.gather(*(log_reader.commits(request=request) for _ in range(10)))

    assert len(workflow_recorder.get_submit_calls_for(workflow=GIT_REPOSITORY_WARM_UP)) == 1
    assert len(recording_cache.set_calls) == 10
    assert sorted(result.warm_up_task_id is not None for result in results) == [False] * 9 + [True]
    assert {result.unavailable_reason for result in results} == {RepositoryGitUnavailableReason.NOT_CLONED}
    assert sorted(result.error_message or "" for result in results) == [WARM_UP_STARTED] + [WARM_UP_PENDING] * 9


async def test_a_warm_up_that_cannot_be_submitted_releases_its_claim(
    git_repos_dir: Path, recording_cache: RecordingCache
) -> None:
    """A held claim with no warm-up behind it would have every worker report one in progress."""
    repository_id = str(uuid.uuid4())
    reader = RepositoryLogReader(cache=recording_cache, workflow=UnreachableWorkflow(), worker_identity=WORKER_IDENTITY)
    request = message_to_request(
        message=_never_cloned_message(repository_id=repository_id, imported_commit=UNKNOWN_COMMIT)
    )

    with pytest.raises(ConnectionError, match=r"^workflow engine unreachable$"):
        await reader.commits(request=request)

    assert recording_cache.storage == {}
    assert [call.key for call in recording_cache.set_calls] == [f"git:warmup:{repository_id}"]


async def test_a_read_write_repository_with_nothing_imported_waits_for_its_sync(
    git_repos_dir: Path,
    log_reader: RepositoryLogReader,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    """The warm-up would not clone it, so starting one would only promise progress that never comes."""
    request = message_to_request(message=_never_cloned_message(repository_id=str(uuid.uuid4()), imported_commit=None))

    result = await log_reader.commits(request=request)

    assert result == CommitLogResult(
        condition=RepositoryGitCondition.UNAVAILABLE,
        unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
        error_message=(
            "The answering worker holds no local copy of this repository yet. "
            "The repository's next sync creates it along with its first import."
        ),
    )
    assert recording_cache.set_calls == []
    assert workflow_recorder.calls == []


async def test_a_read_leaves_the_event_loop_free_for_other_messages(
    git_fixture_repo: InfrahubRepository, clone: Repo, log_reader: RepositoryLogReader
) -> None:
    request = message_to_request(
        message=_message(repository=git_fixture_repo, imported_commit=clone.commit("origin/main").hexsha)
    )
    ticks_while_reading: list[int] = []
    ticks = 0
    reading = True

    async def other_message() -> None:
        nonlocal ticks
        while reading:
            ticks += 1
            await asyncio.sleep(0)

    async def read() -> None:
        nonlocal reading
        try:
            await log_reader.commits(request=request)
            ticks_while_reading.append(ticks)
        finally:
            reading = False

    await asyncio.gather(read(), other_message())

    assert ticks_while_reading[0] > 0


async def test_a_read_does_not_wait_for_the_repository_lock(
    git_fixture_repo: InfrahubRepository,
    clone: Repo,
    repository_lock_held_by_an_import: None,
    log_reader: RepositoryLogReader,
) -> None:
    """An import holds the repository lock for its whole run; a read must not queue behind it."""
    request = message_to_request(
        message=_message(repository=git_fixture_repo, imported_commit=clone.commit("origin/main").hexsha)
    )

    async with asyncio.timeout(10):
        result = await log_reader.commits(request=request)

    assert result.condition is RepositoryGitCondition.IN_SYNC
