from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.exceptions import RepositoryError, RepositoryNotSynchronizedError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger, LoggerAdapter


@dataclass(frozen=True)
class GitMergeTarget:
    """A read-write repository whose part of a branch merge runs in Git."""

    name: str
    location: str
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
    the synchronization imports the head. A remote that cannot be read does not block the merge: the
    guard of the Git merge still compares the heads.
    """

    def __init__(self, reader: RemoteHeadReader, log: Logger | LoggerAdapter[Logger]) -> None:
        self.reader = reader
        self.log = log

    async def check(self, source_branch: str, targets: Sequence[GitMergeTarget]) -> None:
        """Compare, for each repository, the graph commit of both branches with their remote heads.

        Raises:
            RepositoryNotSynchronizedError: When a remote head differs from the commit the graph records.

        """
        unimported: list[UnimportedRemoteHead] = []
        for target in targets:
            expected = {source_branch: target.source_commit, target.remote_trunk: target.destination_commit}
            try:
                heads = await self.reader.read_heads(
                    repository_name=target.name, location=target.location, branch_names=list(expected)
                )
            except RepositoryError as exc:
                self.log.warning(
                    f"Unable to read the remote heads of repository {target.name}, the merge of branch "
                    f"{source_branch} goes on without this check: {exc.message}"
                )
                continue
            unimported.extend(
                UnimportedRemoteHead(
                    repository_name=target.name,
                    remote_branch=remote_branch,
                    remote_head=heads[remote_branch],
                    graph_commit=graph_commit,
                )
                for remote_branch, graph_commit in expected.items()
                if remote_branch in heads and heads[remote_branch] != graph_commit
            )

        if unimported:
            raise RepositoryNotSynchronizedError(
                self._refusal_message(source_branch=source_branch, unimported=unimported)
            )

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
