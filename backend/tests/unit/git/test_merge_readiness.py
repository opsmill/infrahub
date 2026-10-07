"""How a branch merge checks, before the graph merge, that Infrahub imported every remote head its Git merge builds on."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field

import pytest

from infrahub.exceptions import (
    RepositoryCredentialsError,
    RepositoryCredentialsRefusedError,
    RepositoryNotSynchronizedError,
)
from infrahub.git.merge_readiness import GitMergeTarget, RemoteHeadsMergeCheck
from tests.adapters.remote_heads import (
    CountingRemoteHeadReader,
    FailingRemoteHeadReader,
    HeadRead,
    InMemoryRemoteHeadReader,
    StalledRemoteHeadReader,
    TogetherRemoteHeadReader,
)

SOURCE = "feature"
SOURCE_HEAD = "b" * 40
TRUNK_HEAD = "c" * 40
NEWER = "d" * 40
LOGGER_NAME = "tests.merge_readiness"


def target(
    name: str = "network-repo",
    remote_trunk: str = "main",
    source_commit: str | None = SOURCE_HEAD,
    remote_source_branch: str = SOURCE,
) -> GitMergeTarget:
    return GitMergeTarget(
        name=name,
        location=f"https://git.example.com/{name}.git",
        remote_source_branch=remote_source_branch,
        remote_trunk=remote_trunk,
        source_commit=source_commit,
        destination_commit=TRUNK_HEAD,
    )


def check(
    reader: InMemoryRemoteHeadReader | FailingRemoteHeadReader, parallel_reads: int = 8, deadline_seconds: float = 30
) -> RemoteHeadsMergeCheck:
    return RemoteHeadsMergeCheck(
        reader=reader,
        log=logging.getLogger(LOGGER_NAME),
        parallel_reads=parallel_reads,
        deadline_seconds=deadline_seconds,
    )


@dataclass
class UnimportedHeadCase:
    name: str
    targets: list[GitMergeTarget]
    remote_heads: dict[str, dict[str, str]]
    message: str
    expected_reads: list[HeadRead] = field(default_factory=list)


UNIMPORTED_HEAD_CASES = [
    UnimportedHeadCase(
        name="source-moved",
        targets=[target()],
        remote_heads={"network-repo": {SOURCE: NEWER, "main": TRUNK_HEAD}},
        message=(
            f"Unable to merge branch {SOURCE}, because Infrahub has not recorded the latest commit of branch "
            f"{SOURCE} of repository network-repo ({NEWER} on the remote, {SOURCE_HEAD} in Infrahub). Merge again "
            "after Infrahub records the latest commit of that branch."
        ),
    ),
    UnimportedHeadCase(
        name="trunk-the-remote-names-master-moved",
        targets=[target(remote_trunk="master")],
        remote_heads={"network-repo": {SOURCE: SOURCE_HEAD, "master": NEWER}},
        message=(
            f"Unable to merge branch {SOURCE}, because Infrahub has not recorded the latest commit of branch "
            f"master of repository network-repo ({NEWER} on the remote, {TRUNK_HEAD} in Infrahub). Merge again "
            "after Infrahub records the latest commit of that branch."
        ),
        expected_reads=[
            HeadRead(
                repository_name="network-repo",
                location="https://git.example.com/network-repo.git",
                branch_names=(SOURCE, "master"),
            )
        ],
    ),
    UnimportedHeadCase(
        name="no-commit-in-the-graph",
        targets=[target(source_commit=None)],
        remote_heads={"network-repo": {SOURCE: SOURCE_HEAD, "main": TRUNK_HEAD}},
        message=(
            f"Unable to merge branch {SOURCE}, because Infrahub has not recorded the latest commit of branch "
            f"{SOURCE} of repository network-repo ({SOURCE_HEAD} on the remote, no commit in Infrahub). Merge "
            "again after Infrahub records the latest commit of that branch."
        ),
    ),
    UnimportedHeadCase(
        name="source-moved-on-a-repository-whose-branch-records-the-trunk-commit",
        targets=[target(source_commit=TRUNK_HEAD)],
        remote_heads={"network-repo": {SOURCE: NEWER, "main": NEWER}},
        message=(
            f"Unable to merge branch {SOURCE}, because Infrahub has not recorded the latest commit of branch "
            f"{SOURCE} of repository network-repo ({NEWER} on the remote, {TRUNK_HEAD} in Infrahub). Merge again "
            "after Infrahub records the latest commit of that branch."
        ),
        expected_reads=[
            HeadRead(
                repository_name="network-repo",
                location="https://git.example.com/network-repo.git",
                branch_names=(SOURCE,),
            )
        ],
    ),
    UnimportedHeadCase(
        name="two-repositories",
        targets=[target(name="first-repo"), target(name="second-repo")],
        remote_heads={
            "first-repo": {SOURCE: NEWER, "main": TRUNK_HEAD},
            "second-repo": {SOURCE: SOURCE_HEAD, "main": NEWER},
        },
        message=(
            f"Unable to merge branch {SOURCE}, because Infrahub has not recorded the latest commit of branch "
            f"{SOURCE} of repository first-repo ({NEWER} on the remote, {SOURCE_HEAD} in Infrahub); branch main "
            f"of repository second-repo ({NEWER} on the remote, {TRUNK_HEAD} in Infrahub). Merge again after "
            "Infrahub records the latest commit of these branches."
        ),
    ),
]


@pytest.mark.parametrize("case", UNIMPORTED_HEAD_CASES, ids=lambda case: case.name)
async def test_a_remote_head_infrahub_has_not_imported_refuses_the_merge(case: UnimportedHeadCase) -> None:
    reader = InMemoryRemoteHeadReader(heads=case.remote_heads)

    with pytest.raises(RepositoryNotSynchronizedError, match=rf"^{re.escape(case.message)}$"):
        await check(reader=reader).check(source_branch=SOURCE, targets=case.targets)

    if case.expected_reads:
        assert reader.reads == case.expected_reads


async def test_remote_heads_the_graph_records_let_the_merge_go_on() -> None:
    reader = InMemoryRemoteHeadReader(heads={"network-repo": {SOURCE: SOURCE_HEAD, "main": TRUNK_HEAD}})

    await check(reader=reader).check(source_branch=SOURCE, targets=[target()])

    assert reader.reads == [
        HeadRead(
            repository_name="network-repo",
            location="https://git.example.com/network-repo.git",
            branch_names=(SOURCE, "main"),
        )
    ]


async def test_a_branch_the_remote_does_not_hold_lets_the_merge_go_on() -> None:
    """A branch created in Infrahub and never pushed has no remote head to compare."""
    reader = InMemoryRemoteHeadReader(heads={"network-repo": {"main": TRUNK_HEAD}})

    await check(reader=reader).check(source_branch=SOURCE, targets=[target()])


async def test_a_remote_that_cannot_be_read_lets_the_merge_go_on_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    await check(reader=FailingRemoteHeadReader()).check(source_branch=SOURCE, targets=[target()])

    assert [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME] == [
        f"Unable to read the remote heads of repository network-repo, the merge of branch {SOURCE} goes on "
        "without this check: Unable to clone the repository network-repo, please check the address and the "
        "credential"
    ]


async def test_the_remote_heads_of_every_repository_are_read_at_the_same_time() -> None:
    """A merge waits for the slowest remote, not for the sum of them."""
    targets = [target(name=f"repo-{index}") for index in range(3)]
    reader = TogetherRemoteHeadReader(
        heads={target.name: {SOURCE: SOURCE_HEAD, "main": TRUNK_HEAD} for target in targets}, reads_in_flight=3
    )

    await asyncio.wait_for(check(reader=reader).check(source_branch=SOURCE, targets=targets), timeout=10)

    assert [read.repository_name for read in reader.reads] == ["repo-0", "repo-1", "repo-2"]


async def test_a_source_named_like_the_remote_trunk_compares_only_the_trunk_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both names map onto one remote branch, which can hold one head only."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    reader = InMemoryRemoteHeadReader(heads={"network-repo": {"develop": TRUNK_HEAD}})

    await check(reader=reader).check(
        source_branch="develop", targets=[target(remote_trunk="develop", remote_source_branch="develop")]
    )

    assert reader.reads == [
        HeadRead(
            repository_name="network-repo",
            location="https://git.example.com/network-repo.git",
            branch_names=("develop",),
        )
    ]
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME] == [
        "Branch develop has the name of the trunk of repository network-repo on the remote, so the merge "
        "compares only the trunk with its remote head"
    ]


async def test_a_trunk_that_moved_does_not_hold_a_merge_whose_branch_records_the_trunk_commit() -> None:
    """The branch records the trunk commit, so the Git merge of that repository has nothing to push."""
    reader = InMemoryRemoteHeadReader(heads={"network-repo": {SOURCE: TRUNK_HEAD, "main": NEWER}})

    await check(reader=reader).check(source_branch=SOURCE, targets=[target(source_commit=TRUNK_HEAD)])

    assert reader.reads == [
        HeadRead(
            repository_name="network-repo",
            location="https://git.example.com/network-repo.git",
            branch_names=(SOURCE,),
        )
    ]


async def test_the_merge_check_reads_at_most_the_given_number_of_remotes_at_the_same_time() -> None:
    """Each read starts a git process, so a merge over many repositories must not start them all at once."""
    targets = [target(name=f"repo-{index}") for index in range(20)]
    reader = CountingRemoteHeadReader(
        heads={target.name: {SOURCE: SOURCE_HEAD, "main": TRUNK_HEAD} for target in targets}
    )

    await check(reader=reader, parallel_reads=3).check(source_branch=SOURCE, targets=targets)

    assert (reader.most_in_flight, len(reader.reads)) == (3, 20)


async def test_a_remote_that_refuses_the_credentials_refuses_the_merge() -> None:
    """The Git merge would read the remote with the same credentials, and fail after the merge in Infrahub.

    The refusal is one the user can fix, so it is a validation error that keeps the credentials error as its cause.
    """
    message = (
        f"Unable to merge branch {SOURCE}, because Infrahub cannot read the remote of a repository with its "
        "credentials. Authentication failed for network-repo, please validate the credentials. The Git merge "
        "would fail the same way, after the merge in Infrahub. Fix the credentials, then merge again."
    )

    with pytest.raises(RepositoryCredentialsRefusedError, match=rf"^{re.escape(message)}$") as refusal:
        await check(reader=FailingRemoteHeadReader(error_class=RepositoryCredentialsError)).check(
            source_branch=SOURCE, targets=[target()]
        )

    assert type(refusal.value.__cause__) is RepositoryCredentialsError


async def test_a_credentials_error_on_a_repository_whose_branch_records_the_trunk_commit_lets_the_merge_go_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """That repository gets no Git merge, so nothing reads its remote after the merge in Infrahub."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    await check(reader=FailingRemoteHeadReader(error_class=RepositoryCredentialsError)).check(
        source_branch=SOURCE, targets=[target(source_commit=TRUNK_HEAD)]
    )

    assert [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME] == [
        f"Unable to read the remote heads of repository network-repo, the merge of branch {SOURCE} goes on "
        "without this check: Authentication failed for network-repo, please validate the credentials."
    ]


async def test_a_remote_not_read_by_the_deadline_lets_the_merge_go_on_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The check runs before the global merge lock, so all its reads together must stop delaying the merge."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    reader = StalledRemoteHeadReader(
        heads={name: {SOURCE: SOURCE_HEAD, "main": TRUNK_HEAD} for name in ("fast-repo", "slow-repo")},
        stalled={"slow-repo"},
    )

    await asyncio.wait_for(
        check(reader=reader, deadline_seconds=0.1).check(
            source_branch=SOURCE, targets=[target(name="fast-repo"), target(name="slow-repo")]
        ),
        timeout=10,
    )

    assert reader.cancelled == ["slow-repo"]
    assert [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME] == [
        f"Unable to read the remote heads of repository slow-repo within 0.1 seconds, the merge of branch {SOURCE} "
        "goes on without this check"
    ]


async def test_a_merge_with_no_repository_to_read_goes_on() -> None:
    """A branch merge with no Git repository reads no remote and is not held."""
    reader = InMemoryRemoteHeadReader(heads={})

    await check(reader=reader).check(source_branch=SOURCE, targets=[])

    assert reader.reads == []
