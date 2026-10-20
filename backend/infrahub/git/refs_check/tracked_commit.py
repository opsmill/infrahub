"""Reading the commit a read-only repository has imported on one Infrahub branch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class TrackedCommitReader(Protocol):
    """The commit a read-only repository has imported on one Infrahub branch."""

    async def read(self, *, repository_id: str, branch_name: str) -> str | None:
        """Return that commit, or None when the branch has imported none and when the repository is gone."""
        ...


class GraphTrackedCommitReader:
    """Answers from the graph, in a read-only session of its own."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self._db = db

    async def read(self, *, repository_id: str, branch_name: str) -> str | None:
        async with self._db.start_session(read_only=True) as db:
            repository = await NodeManager.get_one(
                db=db,
                id=repository_id,
                kind=CoreReadOnlyRepository,
                branch=branch_name,
                fields={"commit": None},
                raise_on_error=False,
            )
        return repository.commit.value if repository is not None else None
