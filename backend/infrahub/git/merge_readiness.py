from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.exceptions import (
    RepositoryCredentialsError,
    RepositoryCredentialsRefusedError,
    RepositoryError,
    RepositoryNotSynchronizedError,
)
from infrahub.git.commit_id import readable_commit

if TYPE_CHECKING:
    from collections.abc import Sequence
    from logging import Logger, LoggerAdapter


def nothing_to_merge_in_git(source_commit: str | None, destination_commit: str | None) -> bool:
    """Whether the Git merge would push nothing, from the commits the graph stores on both branches.

    That holds when both record the same full commit id, or when neither records a commit, as after a
    failed first clone. A value that is set but is not a full commit id is unknown, so it never counts.
    """
    if not source_commit and not destination_commit:
        return True
    readable = readable_commit(source_commit)
    return readable is not None and readable == readable_commit(destination_commit)


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

    nothing_to_merge: bool
    """Whether the Git merge would push nothing, decided from the values the graph stores."""


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
    """Refuses a branch merge while Infrahub has not recorded a remote head that its Git merge builds on.

    The refusal comes before the graph merge, so the branch stays open and the merge can run again once
    Infrahub records the head. A remote that cannot be reached, or does not answer in time, does not block
    the merge: the Git merge then fetches from the same remote, and when that remote still cannot be
    reached, the Git merge fails after the graph merge. All the reads together stop at one deadline, and a
    repository not read by then does not block the merge either. A remote that refuses the credentials blocks the
    merge when the repository needs a Git merge, because that Git merge would read the remote with the
    same credentials and fail after the graph merge.
    """

    def __init__(
        self,
        reader: RemoteHeadReader,
        log: Logger | LoggerAdapter[Logger],
        parallel_reads: int,
        deadline_seconds: float,
    ) -> None:
        """Build the check.

        Args:
            parallel_reads: The most remotes read at the same time, because each read runs a git process.
            deadline_seconds: The longest time all the reads together may take, because the merge waits for them.

        """
        self.reader = reader
        self.log = log
        self.parallel_reads = parallel_reads
        self.deadline_seconds = deadline_seconds

    async def check(self, source_branch: str, targets: Sequence[GitMergeTarget]) -> None:
        """Compare, for each repository, the graph commit of both branches with their remote heads.

        A repository whose branch records the commit of its trunk has nothing to merge in Git, so its trunk
        can move without holding the merge. Its source branch is still compared: a branch merges once and
        never syncs again. Every other repository compares its trunk, also when the branch changed no file
        of it, because the rule is equality and not ancestry.

        Raises:
            RepositoryCredentialsRefusedError: When a remote refuses the credentials of a repository that needs a Git
                merge.
            RepositoryNotSynchronizedError: When a remote head differs from the commit the graph records.

        """
        expected_heads = [self._expected_heads(source_branch=source_branch, target=target) for target in targets]
        read_heads = await self._read_all_heads(
            source_branch=source_branch, targets=targets, expected_heads=expected_heads
        )
        refused = [read for read in read_heads if isinstance(read, RepositoryCredentialsError)]
        if refused:
            raise RepositoryCredentialsRefusedError(
                f"Unable to merge branch {source_branch}, because Infrahub cannot read the remote of a repository "
                f"with its credentials. {' '.join(error.message for error in refused)} The Git merge would fail "
                "the same way, after the merge in Infrahub. Fix the credentials, then merge again."
            ) from refused[0]

        unimported = [
            UnimportedRemoteHead(
                repository_name=target.name,
                remote_branch=remote_branch,
                remote_head=heads[remote_branch],
                graph_commit=graph_commit,
            )
            for target, expected, heads in zip(targets, expected_heads, read_heads, strict=True)
            if isinstance(heads, dict)
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
        if target.nothing_to_merge:
            return {target.remote_source_branch: target.source_commit}
        return {target.remote_source_branch: target.source_commit, target.remote_trunk: target.destination_commit}

    async def _read_all_heads(
        self, source_branch: str, targets: Sequence[GitMergeTarget], expected_heads: Sequence[dict[str, str | None]]
    ) -> list[dict[str, str] | RepositoryCredentialsError | None]:
        if not targets:
            return []
        reads = asyncio.Semaphore(self.parallel_reads)
        tasks = [
            asyncio.create_task(
                self._read_heads(source_branch=source_branch, target=target, branch_names=list(expected), reads=reads)
            )
            for target, expected in zip(targets, expected_heads, strict=True)
        ]
        try:
            done, _ = await asyncio.wait(tasks, timeout=self.deadline_seconds)
        finally:
            for task in tasks:
                task.cancel()
            # A cancelled read kills its git process, and the merge must not go on before that is done.
            await asyncio.gather(*tasks, return_exceptions=True)

        read_heads: list[dict[str, str] | RepositoryCredentialsError | None] = []
        for target, task in zip(targets, tasks, strict=True):
            if task in done:
                read_heads.append(task.result())
                continue
            self.log.warning(
                f"Unable to read the remote heads of repository {target.name} within {self.deadline_seconds} seconds, "
                f"the merge of branch {source_branch} goes on without this check"
            )
            read_heads.append(None)
        return read_heads

    async def _read_heads(
        self, source_branch: str, target: GitMergeTarget, branch_names: list[str], reads: asyncio.Semaphore
    ) -> dict[str, str] | RepositoryCredentialsError | None:
        try:
            async with reads:
                return await self.reader.read_heads(
                    repository_name=target.name, location=target.location, branch_names=branch_names
                )
        except RepositoryError as exc:
            if isinstance(exc, RepositoryCredentialsError) and not target.nothing_to_merge:
                return exc
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
        branches = "that branch" if len(unimported) == 1 else "these branches"
        return (
            f"Unable to merge branch {source_branch}, because Infrahub has not recorded the latest commit of "
            f"{heads}. Merge again after Infrahub records the latest commit of {branches}."
        )
