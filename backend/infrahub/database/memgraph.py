from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import EntityType, IndexType
from .index import IndexInfo, IndexItem, IndexManagerBase
from .manager import DatabaseManager

if TYPE_CHECKING:
    from . import InfrahubDatabase


class IndexNodeMemgraph(IndexItem):
    def get_add_query(self) -> str:
        properties_str = ", ".join(self.properties)
        return f"CREATE INDEX ON :{self.label}({properties_str})"

    def get_drop_query(self) -> str:
        properties_str = ", ".join(self.properties)
        return f"DROP INDEX ON :{self.label}({properties_str})"


class IndexManagerMemgraph(IndexManagerBase):
    def init(self, nodes: list[IndexItem], rels: list[IndexItem]) -> None:  # noqa: ARG002
        self.nodes = [IndexNodeMemgraph(**item.model_dump()) for item in nodes]
        self.initialized = True

    async def add(self) -> None:
        for item in self.items:
            await self.db.execute_query(query=item.get_add_query(), params={}, name="index_add")

    async def drop(self) -> None:
        for item in self.items:
            await self.db.execute_query(query=item.get_drop_query(), params={}, name="index_drop")

    async def list(self) -> list[IndexInfo]:
        query = "SHOW INDEX INFO"
        records = await self.db.execute_query(query=query, params={}, name="index_show")
        results = []
        for record in records:
            if not record["label"]:
                continue
            results.append(
                IndexInfo(
                    name="n/a",
                    label=record["label"],
                    properties=[record["property"]],
                    type=IndexType.NOT_APPLICABLE,
                    entity_type=EntityType.NODE,  # Memgraph only support Node Indexes
                )
            )

        return results


class DatabaseManagerMemgraph(DatabaseManager):
    def __init__(self, db: InfrahubDatabase) -> None:
        super().__init__(db=db)
        self.index = IndexManagerMemgraph(db=db)
