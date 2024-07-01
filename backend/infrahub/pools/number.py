from dataclasses import dataclass
from typing import Optional, Union

from infrahub.core.node import Node
from infrahub.core.protocols import CoreNode
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


@dataclass
class UsedNumber:
    number: int
    branch: str


class NumberUtilizationGetter:
    def __init__(
        self,
        db: InfrahubDatabase,
        pool: CoreNode,
        at: Optional[Union[Timestamp, str]] = None,
    ) -> None:
        self.db = db
        self.at = at
        self.pool = pool
        self.start_range = int(pool.start_range.value)  # type: ignore[attr-defined]
        self.end_range = int(pool.end_range.value)  # type: ignore[attr-defined]
        self.used: list[UsedNumber] = []
        self.used_default_branch: set[int] = set()
        self.used_branches: set[int] = set()

    async def load_data(self) -> None:
        existing_nodes = await registry.manager.query(
            db=self.db,
            schema=self.pool.node.value,  # type: ignore[attr-defined]
            at=self.at,
            branch_agnostic=True,
        )
        self.used = [
            UsedNumber(number=getattr(node, self.pool.node_attribute.value).value, branch=node._branch.name)  # type: ignore[attr-defined]
            for node in existing_nodes
        ]
        self.used_default_branch = {
            entry.number
            for entry in self.used
            if self.start_range <= entry.number <= self.end_range and entry.branch == registry.default_branch
        }
        used_branches = {
            entry.number
            for entry in self.used
            if self.start_range <= entry.number <= self.end_range and entry.branch != registry.default_branch
        }
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


class NumberUtilizationGettera:
    def __init__(
        self, db: InfrahubDatabase, ip_prefixes: list[Node], at: Optional[Union[Timestamp, str]] = None
    ) -> None:
        self.db = db
        self.ip_prefixes = ip_prefixes
        self.at = at
