from __future__ import annotations

from infrahub.constants.database import EntityType, IndexType
from infrahub.core.query import QueryType

from .index import IndexInfo, IndexItem, IndexManagerBase


class IndexRelNeo4j(IndexItem):
    @property
    def _index_name(self) -> str:
        return f"rel_{self.type.value.lower()}_{self.name}_{'_'.join(self.properties)}"

    def get_add_query(self) -> str:
        properties_str = ", ".join([f"r.{prop}" for prop in self.properties])
        return (
            f"CREATE {self.type.value.upper()} INDEX {self._index_name} IF NOT EXISTS "
            f"FOR ()-[r:{self.label}]-() ON ({properties_str})"
        )

    def get_drop_query(self) -> str:
        return f"DROP INDEX {self._index_name} IF EXISTS"


class IndexNodeNeo4j(IndexItem):
    @property
    def _index_name(self) -> str:
        return f"node_{self.type.value.lower()}_{self.name}_{'_'.join(self.properties)}"

    def get_add_query(self) -> str:
        properties_str = ", ".join([f"n.{prop}" for prop in self.properties])
        return (
            f"CREATE {self.type.value.upper()} INDEX {self._index_name} IF NOT EXISTS "
            f"FOR (n:{self.label}) ON ({properties_str})"
        )

    def get_drop_query(self) -> str:
        return f"DROP INDEX {self._index_name} IF EXISTS"


class IndexManagerNeo4j(IndexManagerBase):
    def init(self, nodes: list[IndexItem], rels: list[IndexItem]) -> None:
        self.nodes = [IndexNodeNeo4j(**item.model_dump()) for item in nodes]
        self.rels = [IndexRelNeo4j(**item.model_dump()) for item in rels]
        self.initialized = True

    async def list(self) -> list[IndexInfo]:
        query = "SHOW INDEXES"
        records = await self.db.execute_query(query=query, params={}, name="index_show", type=QueryType.READ)
        results = []
        for record in records:
            if not record["labelsOrTypes"]:
                continue
            results.append(
                IndexInfo(
                    name=record["name"],
                    label=", ".join(record["labelsOrTypes"]),
                    properties=record["properties"],
                    type=IndexType(str(record["type"]).lower()),
                    entity_type=EntityType(str(record["entityType"]).lower()),
                )
            )

        return results
