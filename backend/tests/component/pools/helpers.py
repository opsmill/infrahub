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
        start: int,
        end: int,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> CoreNumberPoolRange:
        if start == self.failing_start:
            raise RuntimeError("range write failed")
        return await super().create_range(pool=pool, start=start, end=end, weight=weight, at=at, user_id=user_id)
