from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.query.resource_manager import NumberPoolGetAllocated
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreNode
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@dataclass
class UsedNumber:
    number: int
    branch: str


class NumberUtilizationGetter:
    def __init__(self, db: InfrahubDatabase, pool: CoreNode, branch: Branch, at: Timestamp | str | None = None) -> None:
        self.db = db
        self.at = at
        self.pool = pool
        self.branch = branch
        self.start_range = int(pool.start_range.value)  # type: ignore[attr-defined]
        self.end_range = int(pool.end_range.value)  # type: ignore[attr-defined]
        self.used: list[UsedNumber] = []
        self.used_default_branch: set[int] = set()
        self.used_branches: set[int] = set()

    async def load_data(self) -> None:
        query = await NumberPoolGetAllocated.init(db=self.db, pool=self.pool, branch=self.branch, branch_agnostic=True)
        await query.execute(db=self.db)

        self.used = [
            UsedNumber(
                number=result.get_as_type(label="value", return_type=int),
                branch=result.get_as_type(label="branch", return_type=str),
            )
            for result in query.results
            if result.get_as_optional_type(label="value", return_type=int) is not None
        ]

        self.used_default_branch = {entry.number for entry in self.used if entry.branch == registry.default_branch}
        used_branches = {entry.number for entry in self.used if entry.branch != registry.default_branch}
        self.used_branches = used_branches - self.used_default_branch

    @property
    def utilization(self) -> float:
        return ((len(self.used_branches) + len(self.used_default_branch)) / self.total_pool_size) * 100

    @property
    def utilization_branches(self) -> float:
        return (len(self.used_branches) / self.total_pool_size) * 100

    @property
    def utilization_default_branch(self) -> float:
        return (len(self.used_default_branch) / self.total_pool_size) * 100

    @property
    def total_pool_size(self) -> int:
        return self.end_range - self.start_range + 1
