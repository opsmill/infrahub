from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List

from pydantic import BaseModel

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class IndexType(str, Enum):
    TEXT = "text"
    RANGE = "range"
    LOOKUP = "lookup"


class EntityType(str, Enum):
    NODE = "node"
    RELATIONSHIP = "relationship"


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


class IndexRelNeo4j(IndexItem):
    def get_add_query(self) -> str:
        properties_str = ", ".join([f"r.{prop}" for prop in self.properties])
        return (
            f"CREATE {self.type.value.upper()} INDEX rel_{self.type.value.lower()}_{self.name}_{'_'.join(self.properties)}IF NOT EXISTS "
            f"FOR ()-[r:{self.label}]-() ON ({properties_str})"
        )

    def get_drop_query(self) -> str:
        return f"DROP INDEX rel_{self.type.lower()}_{self.name}_{'_'.join(self.properties)} IF EXISTS"


class IndexNodeNeo4j(IndexItem):
    def get_add_query(self) -> str:
        properties_str = ", ".join([f"n.{prop}" for prop in self.properties])
        return (
            f"CREATE {self.type.value.upper()} INDEX node_{self.type.value.lower()}_{self.name}_{'_'.join(self.properties)} IF NOT EXISTS "
            f"FOR (n:{self.label}) ON ({properties_str})"
        )

    def get_drop_query(self) -> str:
        return f"DROP INDEX node_{self.type.lower()}_{self.name}_{'_'.join(self.properties)} IF EXISTS"


class IndexManagerBase:
    def __init__(self, db: InfrahubDatabase, nodes: List[IndexItem], rels: List[IndexItem]):
        self.db = db

        self.nodes: List[IndexItem] = nodes
        self.rels: List[IndexItem] = rels

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


class IndexManagerNeo4j(IndexManagerBase):
    async def list(self) -> List[IndexInfo]:
        query = "SHOW INDEXES"
        records = await self.db.execute_query(query=query, params={}, name="index_show")
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


node_indexes: List[IndexItem] = [
    IndexNodeNeo4j(name="node", label="Node", properties=["uuid"], type=IndexType.RANGE),
    IndexNodeNeo4j(name="attr", label="Attribute", properties=["name"], type=IndexType.RANGE),
    IndexNodeNeo4j(name="attr_value", label="AttributeValue", properties=["value"], type=IndexType.RANGE),
    IndexNodeNeo4j(name="rel_uuid", label="Relationship", properties=["uuid"], type=IndexType.RANGE),
    IndexNodeNeo4j(name="rel_identifier", label="Relationship", properties=["name"], type=IndexType.RANGE),
]

rel_indexes: List[IndexItem] = [
    IndexRelNeo4j(
        name="attr_from",
        label="HAS_ATTRIBUTE",
        properties=["from"],
        type=IndexType.RANGE,
    ),
    IndexRelNeo4j(
        name="attr_branch",
        label="HAS_ATTRIBUTE",
        properties=["branch"],
        type=IndexType.RANGE,
    ),
    IndexRelNeo4j(
        name="value_from",
        label="HAS_VALUE",
        properties=["from"],
        type=IndexType.RANGE,
    ),
    IndexRelNeo4j(
        name="value_branch",
        label="HAS_VALUE",
        properties=["branch"],
        type=IndexType.RANGE,
    ),
]
