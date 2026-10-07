import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from infrahub.exceptions import RepositoryConnectionError


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
    """RemoteHeadReader whose every read fails the way an unreachable remote fails."""

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        raise RepositoryConnectionError(identifier=repository_name)


class TogetherRemoteHeadReader(InMemoryRemoteHeadReader):
    """RemoteHeadReader that answers no read until the given number of reads have all started.

    Reads made one after the other never all start, so they wait forever.
    """

    def __init__(self, heads: dict[str, dict[str, str]], reads_in_flight: int) -> None:
        super().__init__(heads=heads)
        self.reads_in_flight = reads_in_flight
        self.all_started = asyncio.Event()

    async def read_heads(self, repository_name: str, location: str, branch_names: Sequence[str]) -> dict[str, str]:
        heads = await super().read_heads(repository_name=repository_name, location=location, branch_names=branch_names)
        if len(self.reads) == self.reads_in_flight:
            self.all_started.set()
        await self.all_started.wait()
        return heads


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
