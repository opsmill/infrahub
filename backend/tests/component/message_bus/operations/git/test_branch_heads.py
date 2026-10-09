from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from git import Actor, Repo

from infrahub.core.constants import InfrahubKind, RepositoryGitCondition, RepositoryGitUnavailableReason
from infrahub.git.models import GitRepositoryWarmUp
from infrahub.message_bus.messages.git_branch_heads_get import (
    BranchRefInput,
    GitBranchDriftRow,
    GitBranchHeadsGet,
    GitBranchHeadsGetResponse,
    GitBranchHeadsGetResponseData,
)
from infrahub.message_bus.types import KVTTL
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import build_cache, build_message_bus, build_workflow
from infrahub.workflows.catalogue import GIT_REPOSITORY_WARM_UP
from tests.adapters.cache import CacheSetCall, RecordingCache
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fast_depends import Provider

    from infrahub.git import InfrahubRepository
    from tests.conftest import TestHelper

    ReadHeads = Callable[[GitBranchHeadsGet], Awaitable[GitBranchHeadsGetResponseData]]

AUTHOR = Actor("Ada Lovelace", "ada@example.com")
PINNED_FETCH_TIME = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
NEVER_CLONED_NAME = "never-cloned"
NEVER_CLONED_LOCATION = "/tmp/never-cloned"
UNKNOWN_COMMIT = "deadbeef" * 5
BRANCH_COUNT = 12
BEHIND_BRANCHES = ("feature-02", "feature-05", "feature-09")


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
def read_heads(
    helper: TestHelper,
    dependency_provider: Provider,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> ReadHeads:
    """Send a request through the message bus to the handler and return the answer it replied with."""

    async def _read(message: GitBranchHeadsGet) -> GitBranchHeadsGetResponseData:
        bus = await helper.get_message_bus_simulator()
        with (
            override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider),
            override_dependency(build_cache, lambda: recording_cache, dependency_provider=dependency_provider),
            override_dependency(build_workflow, lambda: workflow_recorder, dependency_provider=dependency_provider),
        ):
            reply = await bus.rpc(message=message, response_class=GitBranchHeadsGetResponse)
        assert reply.passed
        return reply.data

    return _read


def _commit(repo: Repo, name: str, day: int) -> str:
    """Commit one new file with a pinned author and date, and return its hash."""
    Path(repo.working_dir, f"{name}.txt").write_text(name, encoding="utf-8")
    repo.index.add([f"{name}.txt"])
    date = f"2099-10-{day:02d}T12:00:00+0000"
    return repo.index.commit(f"Add {name}", author=AUTHOR, committer=AUTHOR, author_date=date, commit_date=date).hexsha


def _commit_on_branch(repo: Repo, branch: str, name: str, day: int) -> str:
    repo.git.checkout(branch)
    try:
        return _commit(repo=repo, name=name, day=day)
    finally:
        repo.git.checkout("main")


def _fetch(clone: Repo) -> None:
    clone.remotes.origin.fetch(prune=True, tags=True, prune_tags=True)
    timestamp = PINNED_FETCH_TIME.timestamp()
    os.utime(Path(clone.git_dir) / "FETCH_HEAD", (timestamp, timestamp))


def _message(
    repository: InfrahubRepository, branches: list[BranchRefInput], repository_kind: str = InfrahubKind.REPOSITORY
) -> GitBranchHeadsGet:
    return GitBranchHeadsGet(
        repository_id=str(repository.id),
        repository_name=repository.name,
        repository_kind=repository_kind,
        location=repository.get_location(),
        branches=branches,
    )


async def test_only_the_branches_whose_remote_moved_read_as_behind(
    git_fixture_repo: InfrahubRepository,
    upstream: Repo,
    clone: Repo,
    read_heads: ReadHeads,
    recording_cache: RecordingCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    first = upstream.head.commit.hexsha
    names = [f"feature-{index:02d}" for index in range(BRANCH_COUNT)]
    for name in names:
        upstream.create_head(name, first)
    heads = {
        name: _commit_on_branch(repo=upstream, branch=name, name=name, day=day)
        for day, name in enumerate(BEHIND_BRANCHES, start=1)
    }
    _fetch(clone=clone)

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            branches=[
                BranchRefInput(branch_name=f"infrahub-{name}", git_ref=name, tracked_commit=first) for name in names
            ],
        )
    )

    assert data.model_dump() == {
        "fetched_at": PINNED_FETCH_TIME,
        "unavailable_reason": None,
        "warm_up_task_id": None,
        "error_message": None,
        "branches": [
            {
                "branch_name": f"infrahub-{name}",
                "git_ref": name,
                "tracked_commit": first,
                "remote_head": heads.get(name, first),
                "condition": RepositoryGitCondition.BEHIND if name in heads else RepositoryGitCondition.IN_SYNC,
            }
            for name in names
        ],
    }
    assert [row.branch_name for row in data.branches if row.condition is RepositoryGitCondition.BEHIND] == [
        "infrahub-feature-02",
        "infrahub-feature-05",
        "infrahub-feature-09",
    ]
    assert recording_cache.set_calls == []
    assert workflow_recorder.calls == []


async def test_each_read_write_row_is_classified_on_its_own(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    """A rewritten row reads as rewritten, since the remote no longer descends from what was imported."""
    first = upstream.head.commit.hexsha
    upstream.create_head("rewritten", first)
    rewritten_from = _commit_on_branch(repo=upstream, branch="rewritten", name="before-rewrite", day=1)
    _fetch(clone=clone)
    upstream.git.branch("-f", "rewritten", first)
    rewritten_head = _commit_on_branch(repo=upstream, branch="rewritten", name="after-rewrite", day=2)
    _fetch(clone=clone)

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            branches=[
                BranchRefInput(branch_name="in-sync", git_ref="main", tracked_commit=first),
                BranchRefInput(branch_name="never-pushed", git_ref="never-pushed", tracked_commit=first),
                BranchRefInput(branch_name="rewritten", git_ref="rewritten", tracked_commit=rewritten_from),
                BranchRefInput(branch_name="nothing-imported", git_ref="main", tracked_commit=None),
            ],
        )
    )

    assert data.unavailable_reason is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="in-sync",
            git_ref="main",
            tracked_commit=first,
            remote_head=first,
            condition=RepositoryGitCondition.IN_SYNC,
        ),
        GitBranchDriftRow(
            branch_name="never-pushed",
            git_ref="never-pushed",
            tracked_commit=first,
            remote_head=None,
            condition=RepositoryGitCondition.NO_REMOTE,
        ),
        GitBranchDriftRow(
            branch_name="rewritten",
            git_ref="rewritten",
            tracked_commit=rewritten_from,
            remote_head=rewritten_head,
            condition=RepositoryGitCondition.REWRITTEN,
        ),
        GitBranchDriftRow(
            branch_name="nothing-imported",
            git_ref="main",
            tracked_commit=None,
            remote_head=first,
            condition=RepositoryGitCondition.NOT_TRACKED,
        ),
    ]


async def test_a_remote_ref_pointing_at_a_missing_commit_has_no_remote(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    """One unreadable remote ref must not fail the read for every other branch."""
    first = upstream.head.commit.hexsha
    upstream.create_head("feature", first)
    feature_head = _commit_on_branch(repo=upstream, branch="feature", name="feature", day=1)
    _fetch(clone=clone)
    Path(clone.git_dir, "refs", "remotes", "origin", "dangling").write_text(f"{UNKNOWN_COMMIT}\n", encoding="utf-8")

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            branches=[
                BranchRefInput(branch_name="in-sync", git_ref="main", tracked_commit=first),
                BranchRefInput(branch_name="dangling", git_ref="dangling", tracked_commit=first),
                BranchRefInput(branch_name="feature", git_ref="feature", tracked_commit=first),
            ],
        )
    )

    assert data.unavailable_reason is None
    assert data.error_message is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="in-sync",
            git_ref="main",
            tracked_commit=first,
            remote_head=first,
            condition=RepositoryGitCondition.IN_SYNC,
        ),
        GitBranchDriftRow(
            branch_name="dangling",
            git_ref="dangling",
            tracked_commit=first,
            remote_head=None,
            condition=RepositoryGitCondition.NO_REMOTE,
        ),
        GitBranchDriftRow(
            branch_name="feature",
            git_ref="feature",
            tracked_commit=first,
            remote_head=feature_head,
            condition=RepositoryGitCondition.BEHIND,
        ),
    ]


async def test_a_remote_ref_pointing_at_a_tree_has_no_remote(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    """A ref naming a tree rather than a commit must not fail the read for every other branch."""
    first = upstream.head.commit.hexsha
    upstream.create_head("feature", first)
    feature_head = _commit_on_branch(repo=upstream, branch="feature", name="feature", day=1)
    _fetch(clone=clone)
    tree = clone.commit(first).tree.hexsha
    Path(clone.git_dir, "refs", "remotes", "origin", "at-tree").write_text(f"{tree}\n", encoding="utf-8")

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            branches=[
                BranchRefInput(branch_name="in-sync", git_ref="main", tracked_commit=first),
                BranchRefInput(branch_name="at-tree", git_ref="at-tree", tracked_commit=first),
                BranchRefInput(branch_name="feature", git_ref="feature", tracked_commit=first),
            ],
        )
    )

    assert data.unavailable_reason is None
    assert data.error_message is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="in-sync",
            git_ref="main",
            tracked_commit=first,
            remote_head=first,
            condition=RepositoryGitCondition.IN_SYNC,
        ),
        GitBranchDriftRow(
            branch_name="at-tree",
            git_ref="at-tree",
            tracked_commit=first,
            remote_head=None,
            condition=RepositoryGitCondition.NO_REMOTE,
        ),
        GitBranchDriftRow(
            branch_name="feature",
            git_ref="feature",
            tracked_commit=first,
            remote_head=feature_head,
            condition=RepositoryGitCondition.BEHIND,
        ),
    ]


async def test_an_annotated_tag_whose_target_is_missing_reads_as_missing(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    """The tag object names its target without the clone holding it, which must not fail every other row."""
    first = upstream.head.commit.hexsha
    _fetch(clone=clone)
    tag_body = Path(clone.git_dir, "missing-target-tag")
    tag_body.write_text(
        f"object {UNKNOWN_COMMIT}\ntype commit\ntag v-missing\ntagger {AUTHOR.name} <{AUTHOR.email}> 0 +0000\n\nGone\n",
        encoding="utf-8",
    )
    tag_object = clone.git.hash_object("-t", "tag", "-w", "--literally", str(tag_body))
    Path(clone.git_dir, "refs", "tags", "v-missing").write_text(f"{tag_object}\n", encoding="utf-8")

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            branches=[
                BranchRefInput(branch_name="in-sync", git_ref="main", tracked_commit=first),
                BranchRefInput(branch_name="missing-target", git_ref="v-missing", tracked_commit=first),
            ],
        )
    )

    assert data.unavailable_reason is None
    assert data.error_message is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="in-sync",
            git_ref="main",
            tracked_commit=first,
            remote_head=first,
            condition=RepositoryGitCondition.IN_SYNC,
        ),
        GitBranchDriftRow(
            branch_name="missing-target",
            git_ref="v-missing",
            tracked_commit=first,
            remote_head=None,
            condition=RepositoryGitCondition.REF_MISSING,
        ),
    ]


async def test_a_read_only_ref_deleted_upstream_reads_as_missing(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    """The local branch the clone checked out survives the deletion and must not stand in for the remote."""
    first = upstream.head.commit.hexsha
    upstream.create_head("release", first)
    imported = _commit_on_branch(repo=upstream, branch="release", name="release", day=1)
    tagged = _commit(repo=upstream, name="tagged", day=2)
    upstream.create_tag("v1.0", ref=tagged, message="Release 1.0")
    _fetch(clone=clone)
    clone.create_head("release", "origin/release")
    upstream.delete_head("release", force=True)
    _fetch(clone=clone)

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            branches=[
                BranchRefInput(branch_name="deleted-ref", git_ref="release", tracked_commit=imported),
                BranchRefInput(branch_name="tag-ref", git_ref="v1.0", tracked_commit=tagged),
            ],
        )
    )

    assert data.unavailable_reason is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="deleted-ref",
            git_ref="release",
            tracked_commit=imported,
            remote_head=None,
            condition=RepositoryGitCondition.REF_MISSING,
        ),
        GitBranchDriftRow(
            branch_name="tag-ref",
            git_ref="v1.0",
            tracked_commit=tagged,
            remote_head=tagged,
            condition=RepositoryGitCondition.IN_SYNC,
        ),
    ]


async def test_a_branch_name_containing_origin_reads_with_its_own_head(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    first = upstream.head.commit.hexsha
    upstream.create_head("team/origin/x", first)
    head = _commit_on_branch(repo=upstream, branch="team/origin/x", name="team-origin-x", day=1)
    _fetch(clone=clone)

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            branches=[BranchRefInput(branch_name="team-x", git_ref="team/origin/x", tracked_commit=first)],
        )
    )

    assert data.unavailable_reason is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="team-x",
            git_ref="team/origin/x",
            tracked_commit=first,
            remote_head=head,
            condition=RepositoryGitCondition.BEHIND,
        )
    ]


async def test_packed_refs_read_with_their_heads(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    """Git moves refs into one packed file, leaving no loose ref file to read."""
    first = upstream.head.commit.hexsha
    upstream.create_head("feature", first)
    feature_head = _commit_on_branch(repo=upstream, branch="feature", name="feature", day=1)
    tagged = _commit(repo=upstream, name="tagged", day=2)
    upstream.create_tag("v3.0", ref=tagged, message="Release 3.0")
    _fetch(clone=clone)
    clone.git.pack_refs("--all")
    assert not Path(clone.git_dir, "refs", "remotes", "origin", "feature").exists()
    assert not Path(clone.git_dir, "refs", "tags", "v3.0").exists()

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            branches=[
                BranchRefInput(branch_name="feature", git_ref="feature", tracked_commit=first),
                BranchRefInput(branch_name="tag-ref", git_ref="v3.0", tracked_commit=tagged),
            ],
        )
    )

    assert data.unavailable_reason is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="feature",
            git_ref="feature",
            tracked_commit=first,
            remote_head=feature_head,
            condition=RepositoryGitCondition.BEHIND,
        ),
        GitBranchDriftRow(
            branch_name="tag-ref",
            git_ref="v3.0",
            tracked_commit=tagged,
            remote_head=tagged,
            condition=RepositoryGitCondition.IN_SYNC,
        ),
    ]


async def test_a_read_only_ref_pinned_to_a_commit_reads_with_that_commit_as_head(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    pinned = upstream.head.commit.hexsha
    _commit(repo=upstream, name="after-pin", day=1)
    _fetch(clone=clone)

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            branches=[BranchRefInput(branch_name="pinned", git_ref=pinned, tracked_commit=pinned)],
        )
    )

    assert data.unavailable_reason is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="pinned",
            git_ref=pinned,
            tracked_commit=pinned,
            remote_head=pinned,
            condition=RepositoryGitCondition.IN_SYNC,
        )
    ]


async def test_a_read_write_ref_named_like_a_tag_has_no_remote(
    git_fixture_repo: InfrahubRepository, upstream: Repo, clone: Repo, read_heads: ReadHeads
) -> None:
    """A read-write repository tracks branches only, so a tag of the same name must not stand in for one."""
    first = upstream.head.commit.hexsha
    tagged = _commit(repo=upstream, name="tagged", day=1)
    upstream.create_tag("v2.0", ref=tagged, message="Release 2.0")
    _fetch(clone=clone)

    data = await read_heads(
        _message(
            repository=git_fixture_repo,
            branches=[BranchRefInput(branch_name="release", git_ref="v2.0", tracked_commit=first)],
        )
    )

    assert data.unavailable_reason is None
    assert data.branches == [
        GitBranchDriftRow(
            branch_name="release",
            git_ref="v2.0",
            tracked_commit=first,
            remote_head=None,
            condition=RepositoryGitCondition.NO_REMOTE,
        )
    ]


async def test_a_read_write_repository_with_nothing_imported_starts_no_warm_up(
    git_repos_dir: Path, read_heads: ReadHeads, recording_cache: RecordingCache, workflow_recorder: WorkflowRecorder
) -> None:
    """The repository's next sync creates the clone with its first import, so no worker claims a warm-up."""
    data = await read_heads(
        GitBranchHeadsGet(
            repository_id=str(uuid.uuid4()),
            repository_name=NEVER_CLONED_NAME,
            repository_kind=InfrahubKind.REPOSITORY,
            location=NEVER_CLONED_LOCATION,
            branches=[
                BranchRefInput(branch_name="main", git_ref="main", tracked_commit=None),
                BranchRefInput(branch_name="feature", git_ref="feature", tracked_commit=None),
            ],
        )
    )

    assert data.model_dump() == {
        "fetched_at": None,
        "unavailable_reason": RepositoryGitUnavailableReason.NOT_CLONED,
        "warm_up_task_id": None,
        "error_message": (
            "The answering worker holds no local copy of this repository yet. "
            "The repository's next sync creates it along with its first import."
        ),
        "branches": [],
    }
    assert recording_cache.set_calls == []
    assert workflow_recorder.calls == []


async def test_a_worker_without_a_clone_starts_a_warm_up_for_a_tracked_branch(
    git_repos_dir: Path, read_heads: ReadHeads, recording_cache: RecordingCache, workflow_recorder: WorkflowRecorder
) -> None:
    """The first row has nothing imported, so the warm-up runs for the first row that has, as a read-write repository needs."""
    repository_id = str(uuid.uuid4())

    data = await read_heads(
        GitBranchHeadsGet(
            repository_id=repository_id,
            repository_name=NEVER_CLONED_NAME,
            repository_kind=InfrahubKind.REPOSITORY,
            location=NEVER_CLONED_LOCATION,
            branches=[
                BranchRefInput(branch_name="nothing-imported", git_ref="main", tracked_commit=None),
                BranchRefInput(branch_name="imported", git_ref="imported", tracked_commit=UNKNOWN_COMMIT),
            ],
        )
    )

    assert data.unavailable_reason is RepositoryGitUnavailableReason.NOT_CLONED
    assert data.error_message == (
        "The answering worker holds no local copy of this repository yet. A warm-up has been started."
    )
    assert data.warm_up_task_id is not None
    assert str(uuid.UUID(data.warm_up_task_id)) == data.warm_up_task_id
    assert data.branches == []
    assert data.fetched_at is None
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
                    infrahub_branch_name="imported",
                )
            },
            "tags": [],
        }
    ]
