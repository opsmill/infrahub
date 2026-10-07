from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.exceptions import RepositoryError, RepositoryNotSynchronizedError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger, LoggerAdapter


def nothing_to_merge_in_git(source_commit: str | None, destination_commit: str | None) -> bool:
    """Whether the branch records the commit the default branch records, so the Git merge would push nothing."""
    return source_commit is not None and source_commit == destination_commit


@dataclass(frozen=True)
class GitMergeTarget:
    """A read-write repository whose part of a branch merge runs in Git."""

    name: str
    location: str
    remote_source_branch: str
    """The remote branch the source of the merge maps onto."""

    remote_trunk: str
    """The remote branch the repository maps onto the destination of the merge."""

    source_commit: str | None
    """The commit the graph records on the source branch."""

    destination_commit: str | None
    """The commit the graph records on the destination branch."""


@dataclass(frozen=True)
class UnimportedRemoteHead:
    repository_name: str
    remote_branch: str
    remote_head: str
    graph_commit: str | None


class RemoteHeadReader(Protocol):
    """Reads the head commits of a remote without a clone.

    Implementations raise RepositoryError for every failure, so the logic above them handles one
    exception type and imports no git library.
    """

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        """Return the head of each named branch the remote holds. A branch it does not hold is absent."""
        ...


class RemoteHeadsMergeCheck:
    """Refuses a branch merge while Infrahub has not imported a remote head that its Git merge builds on.

    The refusal comes before the graph merge, so the branch stays open and the merge can run again once
    the synchronization imports the head. A remote that cannot be read does not block the merge. The Git
    merge then fetches from the same remote, and when that remote still cannot be read, the Git merge
    fails after the graph merge.
    """

    def __init__(self, reader: RemoteHeadReader, log: Logger | LoggerAdapter[Logger]) -> None:
        self.reader = reader
        self.log = log

    async def check(self, source_branch: str, targets: Sequence[GitMergeTarget]) -> None:
        """Compare, for each repository, the graph commit of both branches with their remote heads.

        A repository the branch did not change has nothing to merge in Git, so its trunk can move without
        holding the merge. Its source branch is still compared: a branch merges once and never syncs again.

        Raises:
            RepositoryNotSynchronizedError: When a remote head differs from the commit the graph records.

        """
        expected_heads = [self._expected_heads(source_branch=source_branch, target=target) for target in targets]
        read_heads = await asyncio.gather(
            *(
                self._read_heads(source_branch=source_branch, target=target, branch_names=list(expected))
                for target, expected in zip(targets, expected_heads, strict=True)
            )
        )
        unimported = [
            UnimportedRemoteHead(
                repository_name=target.name,
                remote_branch=remote_branch,
                remote_head=heads[remote_branch],
                graph_commit=graph_commit,
            )
            for target, expected, heads in zip(targets, expected_heads, read_heads, strict=True)
            if heads is not None
            for remote_branch, graph_commit in expected.items()
            if remote_branch in heads and heads[remote_branch] != graph_commit
        ]

        if unimported:
            raise RepositoryNotSynchronizedError(
                self._refusal_message(source_branch=source_branch, unimported=unimported)
            )

    def _expected_heads(self, source_branch: str, target: GitMergeTarget) -> dict[str, str | None]:
        if target.remote_source_branch == target.remote_trunk:
            self.log.warning(
                f"Branch {source_branch} has the name of the trunk of repository {target.name} on the remote, "
                "so the merge compares only the trunk with its remote head"
            )
            return {target.remote_trunk: target.destination_commit}
        if nothing_to_merge_in_git(source_commit=target.source_commit, destination_commit=target.destination_commit):
            return {target.remote_source_branch: target.source_commit}
        return {target.remote_source_branch: target.source_commit, target.remote_trunk: target.destination_commit}

    async def _read_heads(
        self, source_branch: str, target: GitMergeTarget, branch_names: list[str]
    ) -> dict[str, str] | None:
        try:
            return await self.reader.read_heads(
                repository_name=target.name, location=target.location, branch_names=branch_names
            )
        except RepositoryError as exc:
            self.log.warning(
                f"Unable to read the remote heads of repository {target.name}, the merge of branch "
                f"{source_branch} goes on without this check: {exc.message}"
            )
            return None

    def _refusal_message(self, source_branch: str, unimported: Sequence[UnimportedRemoteHead]) -> str:
        heads = "; ".join(
            f"branch {head.remote_branch} of repository {head.repository_name} ({head.remote_head} on the "
            f"remote, {head.graph_commit or 'no commit'} in Infrahub)"
            for head in unimported
        )
        return (
            f"Unable to merge branch {source_branch}, because Infrahub has not imported the latest commit of "
            f"{heads}. Merge again after the next synchronization of the repository imports it."
        )
