import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from infrahub.exceptions import RepositoryConnectionError, RepositoryError


@dataclass(frozen=True)
class HeadRead:
    repository_name: str
    location: str
    branch_names: tuple[str, ...]


class InMemoryRemoteHeadReader:
    """RemoteHeadReader that answers from the heads given per repository, and keeps every read in order."""

    def __init__(self, heads: dict[str, dict[str, str]]) -> None:
        self.heads = heads
        self.reads: list[HeadRead] = []

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        self.reads.append(
            HeadRead(repository_name=repository_name, location=location, branch_names=tuple(branch_names))
        )
        held = self.heads.get(repository_name, {})
        return {branch_name: held[branch_name] for branch_name in branch_names if branch_name in held}


class FailingRemoteHeadReader:
    """RemoteHeadReader whose every read fails with the given error, an unreachable remote by default."""

    def __init__(self, error_class: type[RepositoryError] = RepositoryConnectionError) -> None:
        self.error_class = error_class

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        raise self.error_class(identifier=repository_name)


class CountingRemoteHeadReader(InMemoryRemoteHeadReader):
    """RemoteHeadReader that keeps the highest number of reads that were in flight at the same time."""

    def __init__(self, heads: dict[str, dict[str, str]]) -> None:
        super().__init__(heads=heads)
        self.in_flight = 0
        self.most_in_flight = 0

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        self.in_flight += 1
        self.most_in_flight = max(self.most_in_flight, self.in_flight)
        try:
            # Every read that can start does start before this one ends.
            await asyncio.sleep(0)
            return await super().read_heads(
                repository_name=repository_name, location=location, branch_names=branch_names
            )
        finally:
            self.in_flight -= 1


class StalledRemoteHeadReader(InMemoryRemoteHeadReader):
    """RemoteHeadReader whose reads of the given repositories never answer, and that keeps every read it cancels."""

    def __init__(self, heads: dict[str, dict[str, str]], stalled: set[str]) -> None:
        super().__init__(heads=heads)
        self.stalled = stalled
        self.cancelled: list[str] = []

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        if repository_name in self.stalled:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.append(repository_name)
                raise
        return await super().read_heads(repository_name=repository_name, location=location, branch_names=branch_names)
