"""How a branch merge checks, before the graph merge, that Infrahub imported every remote head its Git merge builds on."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import pytest

from infrahub.exceptions import RepositoryNotSynchronizedError
from infrahub.git.merge_readiness import GitMergeTarget, RemoteHeadsMergeCheck
from tests.adapters.remote_heads import FailingRemoteHeadReader, HeadRead, InMemoryRemoteHeadReader

SOURCE = "feature"
SOURCE_HEAD = "b" * 40
TRUNK_HEAD = "c" * 40
NEWER = "d" * 40
LOGGER_NAME = "tests.merge_readiness"


def target(
    name: str = "network-repo", remote_trunk: str = "main", source_commit: str | None = SOURCE_HEAD
) -> GitMergeTarget:
    return GitMergeTarget(
        name=name,
        location=f"https://git.example.com/{name}.git",
        remote_trunk=remote_trunk,
        source_commit=source_commit,
        destination_commit=TRUNK_HEAD,
    )


def check(reader: InMemoryRemoteHeadReader | FailingRemoteHeadReader) -> RemoteHeadsMergeCheck:
    return RemoteHeadsMergeCheck(reader=reader, log=logging.getLogger(LOGGER_NAME))


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
            f"Unable to merge branch {SOURCE}, because Infrahub has not imported the latest commit of branch "
            f"{SOURCE} of repository network-repo ({NEWER} on the remote, {SOURCE_HEAD} in Infrahub). Merge again "
            "after the next synchronization of the repository imports it."
        ),
    ),
    UnimportedHeadCase(
        name="trunk-the-remote-names-master-moved",
        targets=[target(remote_trunk="master")],
        remote_heads={"network-repo": {SOURCE: SOURCE_HEAD, "master": NEWER}},
        message=(
            f"Unable to merge branch {SOURCE}, because Infrahub has not imported the latest commit of branch "
            f"master of repository network-repo ({NEWER} on the remote, {TRUNK_HEAD} in Infrahub). Merge again "
            "after the next synchronization of the repository imports it."
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
            f"Unable to merge branch {SOURCE}, because Infrahub has not imported the latest commit of branch "
            f"{SOURCE} of repository network-repo ({SOURCE_HEAD} on the remote, no commit in Infrahub). Merge "
            "again after the next synchronization of the repository imports it."
        ),
    ),
    UnimportedHeadCase(
        name="two-repositories",
        targets=[target(name="first-repo"), target(name="second-repo")],
        remote_heads={
            "first-repo": {SOURCE: NEWER, "main": TRUNK_HEAD},
            "second-repo": {SOURCE: SOURCE_HEAD, "main": NEWER},
        },
        message=(
            f"Unable to merge branch {SOURCE}, because Infrahub has not imported the latest commit of branch "
            f"{SOURCE} of repository first-repo ({NEWER} on the remote, {SOURCE_HEAD} in Infrahub); branch main "
            f"of repository second-repo ({NEWER} on the remote, {TRUNK_HEAD} in Infrahub). Merge again after the "
            "next synchronization of the repository imports it."
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
