from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

from infrahub.constants.database import EntityType, IndexType  # noqa: TC001

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class IndexInfo(BaseModel):
    name: str
    label: str
    properties: list[str]
    type: IndexType
    entity_type: EntityType


class IndexItem(BaseModel):
    name: str
    label: str
    properties: list[str]
    type: IndexType

    def get_add_query(self) -> str:
        raise NotImplementedError()

    def get_drop_query(self) -> str:
        raise NotImplementedError()


class IndexManagerBase(ABC):
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

        self.nodes: list[IndexItem] = []
        self.rels: list[IndexItem] = []
        self.initialized: bool = False

    def init(self, nodes: list[IndexItem], rels: list[IndexItem]) -> None:
        self.nodes = nodes
        self.rels = rels
        self.initialized = True

    @property
    def items(self) -> list[IndexItem]:
        return self.nodes + self.rels

    async def add(self) -> None:
        async with self.db.start_transaction() as dbt:
            for item in self.items:
                await dbt.execute_query(query=item.get_add_query(), params={}, name="index_add")

    async def drop(self) -> None:
        async with self.db.start_transaction() as dbt:
            for item in self.items:
                await dbt.execute_query(query=item.get_drop_query(), params={}, name="index_drop")

    @abstractmethod
    async def list(self) -> list[IndexInfo]:
        pass
