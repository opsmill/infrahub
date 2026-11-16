from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPoolRange
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_repository import NumberPoolRepository


class NumberPoolRepositoryFailingOnRange(NumberPoolRepository):
    """Writes ranges to the database but refuses the one starting at a given number."""

    def __init__(self, db: InfrahubDatabase, failing_start: int) -> None:
        super().__init__(db=db)
        self.failing_start = failing_start

    async def create_range(
        self,
        pool: Node,
        start: int | None,
        end: int | None,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> CoreNumberPoolRange:
        if start == self.failing_start:
            raise RuntimeError("range write failed")
        return await super().create_range(pool=pool, start=start, end=end, weight=weight, at=at, user_id=user_id)


class NumberPoolRepositoryFailingOnDelete(NumberPoolRepository):
    """Writes ranges to the database but refuses to delete any."""

    async def delete_range(
        self, pool_range: CoreNumberPoolRange, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None:
        raise RuntimeError("range delete failed")


RecordedWrite = tuple[str, int | None, int | None]


class NumberPoolRepositoryRecordingWrites(NumberPoolRepository):
    """Writes ranges and shorthands to the database and records each write, in order."""

    def __init__(self, db: InfrahubDatabase) -> None:
        super().__init__(db=db)
        self._writes: list[RecordedWrite] = []

    def get_writes(self) -> list[RecordedWrite]:
        return list(self._writes)

    async def save_shorthand(
        self, pool: Node, start: int | None, end: int | None, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None:
        self._writes.append(("shorthand", start, end))
        await super().save_shorthand(pool=pool, start=start, end=end, at=at, user_id=user_id)

    async def create_range(
        self,
        pool: Node,
        start: int | None,
        end: int | None,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> CoreNumberPoolRange:
        self._writes.append(("create", start, end))
        return await super().create_range(pool=pool, start=start, end=end, weight=weight, at=at, user_id=user_id)

    async def save_range(
        self,
        pool_range: CoreNumberPoolRange,
        start: int | None,
        end: int | None,
        weight: int | None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        self._writes.append(("save", start, end))
        await super().save_range(pool_range=pool_range, start=start, end=end, weight=weight, at=at, user_id=user_id)

    async def delete_range(
        self, pool_range: CoreNumberPoolRange, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None:
        self._writes.append(("delete", pool_range.start.value, pool_range.end.value))
        await super().delete_range(pool_range=pool_range, at=at, user_id=user_id)


class NumberPoolRepositoryRecordingWritesFactory:
    """Builds repositories that record their writes, and returns the writes of every repository it built."""

    def __init__(self) -> None:
        self._repositories: list[NumberPoolRepositoryRecordingWrites] = []

    def __call__(self, db: InfrahubDatabase) -> NumberPoolRepositoryRecordingWrites:
        repository = NumberPoolRepositoryRecordingWrites(db=db)
        self._repositories.append(repository)
        return repository

    def get_writes(self) -> list[RecordedWrite]:
        """Return the writes of each repository in the order the repositories were built."""
        return [write for repository in self._repositories for write in repository.get_writes()]
