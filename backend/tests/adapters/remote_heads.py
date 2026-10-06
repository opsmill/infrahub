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
