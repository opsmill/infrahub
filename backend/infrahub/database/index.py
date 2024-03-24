from __future__ import annotations

from typing import TYPE_CHECKING, List

from pydantic import BaseModel

from .constants import EntityType, IndexType  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class IndexInfo(BaseModel):
    name: str
    label: str
    properties: List[str]
    type: IndexType
    entity_type: EntityType


class IndexItem(BaseModel):
    name: str
    label: str
    properties: List[str]
    type: IndexType

    def get_add_query(self) -> str:
        raise NotImplementedError()

    def get_drop_query(self) -> str:
        raise NotImplementedError()


class IndexManagerBase:
    def __init__(self, db: InfrahubDatabase):
        self.db = db

        self.nodes: List[IndexItem] = []
        self.rels: List[IndexItem] = []
        self.initialized: bool = False

    def init(self, nodes: List[IndexItem], rels: List[IndexItem]) -> None:
        self.nodes = nodes
        self.rels = rels
        self.initialized = True

    @property
    def items(self) -> List[IndexItem]:
        return self.nodes + self.rels

    async def add(self) -> None:
        async with self.db.start_transaction() as dbt:
            for item in self.items:
                await dbt.execute_query(query=item.get_add_query(), params={}, name="index_add")

    async def drop(self) -> None:
        async with self.db.start_transaction() as dbt:
            for item in self.items:
                await dbt.execute_query(query=item.get_drop_query(), params={}, name="index_drop")

    async def list(self) -> List[IndexInfo]:
        raise NotImplementedError()
