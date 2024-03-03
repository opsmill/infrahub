from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Type

from pydantic import BaseModel
from typing_extensions import Self

from infrahub.database import DatabaseType, InfrahubDatabase


class GraphPropertyType(str, Enum):
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    ZONED_DATETIME = "ZONED DATETIME"


class ConstraintInfo(BaseModel):
    item_name: str
    item_label: str
    property: str


class ConstraintItem(ConstraintInfo):
    type: GraphPropertyType
    mandatory: bool = True

    def get_add_queries(self) -> List[str]:
        raise NotImplementedError()

    def get_drop_queries(self) -> List[str]:
        raise NotImplementedError()


class ConstraintItemNeo4j(ConstraintItem):
    def names(self) -> List[str]:
        if self.mandatory:
            return [self.name_main, self.name_exist]
        return [self.name_main]

    @property
    def name_main(self) -> str:
        raise NotImplementedError()

    @property
    def name_exist(self) -> str:
        raise NotImplementedError()

    def get_query_main_add(self) -> str:
        raise NotImplementedError()

    def get_query_exist_add(self) -> str:
        raise NotImplementedError()

    def get_query_main_drop(self) -> str:
        return f"DROP CONSTRAINT {self.name_main} IF EXISTS"

    def get_query_exist_drop(self) -> str:
        return f"DROP CONSTRAINT {self.name_exist} IF EXISTS"

    def get_add_queries(self) -> List[str]:
        queries = [self.get_query_main_add()]
        if self.mandatory:
            queries.append(self.get_query_exist_add())
        return queries

    def get_drop_queries(self) -> List[str]:
        queries = [self.get_query_main_drop()]
        if self.mandatory:
            queries.append(self.get_query_exist_drop())
        return queries


class ConstraintNodeNeo4j(ConstraintItemNeo4j):
    @property
    def name_main(self) -> str:
        return f"node_{self.item_name}_{self.property}_type"

    @property
    def name_exist(self) -> str:
        if not self.mandatory:
            raise ValueError()
        return f"node_{self.item_name}_{self.property}_exist"

    def get_query_main_add(self) -> str:
        return (
            f"CREATE CONSTRAINT {self.name_main} IF NOT EXISTS "
            f"FOR (n:{self.item_label}) REQUIRE n.{self.property} IS :: {self.type.value}"
        )

    def get_query_exist_add(self) -> str:
        return (
            f"CREATE CONSTRAINT {self.name_exist} IF NOT EXISTS "
            f"FOR (n:{self.item_label}) REQUIRE n.{self.property} IS NOT NULL"
        )


class ConstraintRelNeo4j(ConstraintItemNeo4j):
    @property
    def name_main(self) -> str:
        return f"rel_{self.item_name}_{self.property}_type"

    @property
    def name_exist(self) -> str:
        if not self.mandatory:
            raise ValueError()
        return f"rel_{self.item_name}_{self.property}_exist"

    def get_query_main_add(self) -> str:
        return (
            f"CREATE CONSTRAINT {self.name_main} IF NOT EXISTS "
            f"FOR ()-[r:{self.item_label}]-() REQUIRE r.{self.property} IS :: {self.type.value}"
        )

    def get_query_exist_add(self) -> str:
        return (
            f"CREATE CONSTRAINT {self.name_exist} IF NOT EXISTS "
            f"FOR ()-[r:{self.item_label}]-() REQUIRE r.{self.property} IS NOT NULL"
        )


# ------------------------------------------------------
# Memgraph
# ------------------------------------------------------


class ConstraintItemMemgraph(ConstraintItem):
    def get_query_exist_add(self) -> str:
        raise NotImplementedError()

    def get_query_exist_drop(self) -> str:
        raise NotImplementedError()

    def get_add_queries(self) -> List[str]:
        return [self.get_query_exist_add()]

    def get_drop_queries(self) -> List[str]:
        return [self.get_query_exist_drop()]


class ConstraintNodeMemgraph(ConstraintItemMemgraph):
    def get_query_exist_add(self) -> str:
        return f"CREATE CONSTRAINT ON (n:{self.item_label}) ASSERT EXISTS (n.{self.property})"

    def get_query_exist_drop(self) -> str:
        return f"DROP CONSTRAINT ON (n:{self.item_label}) ASSERT EXISTS (n.{self.property})"


TYPE_MAPPING = {
    str: GraphPropertyType.STRING,
    int: GraphPropertyType.INTEGER,
    bool: GraphPropertyType.BOOLEAN,
    float: GraphPropertyType.FLOAT,
}


class ConstraintManager:
    def __init__(self, db: InfrahubDatabase):
        self.db = db

        self.constraint_node_class: Optional[Type[ConstraintItem]] = None
        self.constraint_rel_class: Optional[Type[ConstraintItem]] = None

        if self.db.db_type == DatabaseType.NEO4J:
            self.constraint_node_class = ConstraintNodeNeo4j
            self.constraint_rel_class = ConstraintRelNeo4j
        if self.db.db_type == DatabaseType.MEMGRAPH:
            self.constraint_node_class = ConstraintNodeMemgraph

        self.nodes: List[ConstraintItem] = []
        self.rels: List[ConstraintItem] = []

    @property
    def items(self) -> List[ConstraintItem]:
        return self.nodes + self.rels

    @classmethod
    def from_graph_schema(cls, db: InfrahubDatabase, schema: Dict[str, BaseModel]) -> Self:
        manager = cls(db=db)

        # Process the nodes first
        for _, schema_item in schema.items():
            properties_class: BaseModel = schema_item.model_fields["properties"].annotation  # type: ignore[assignment]
            default_label = str(schema_item.model_fields["default_label"].default)
            for field_name, field in properties_class.model_fields.items():
                clean_field_name = field.alias or field_name
                if field.annotation not in TYPE_MAPPING or not manager.constraint_node_class:
                    continue

                manager.nodes.append(
                    manager.constraint_node_class(
                        item_name=default_label.lower(),
                        item_label=default_label,
                        property=clean_field_name,
                        type=TYPE_MAPPING[field.annotation],
                    )
                )

        return manager

    async def add(self) -> None:
        if self.db.db_type == DatabaseType.MEMGRAPH:
            for item in self.items:
                for query in item.get_add_queries():
                    await self.db.execute_query(query=query, params={}, name="constraint_add")

        else:
            async with self.db.start_transaction() as dbt:
                for item in self.items:
                    for query in item.get_add_queries():
                        await dbt.execute_query(query=query, params={}, name="constraint_add")

    async def drop(self) -> None:
        if self.db.db_type == DatabaseType.MEMGRAPH:
            for item in self.items:
                for query in item.get_drop_queries():
                    await self.db.execute_query(query=query, params={}, name="constraint_drop")
        else:
            async with self.db.start_transaction() as dbt:
                for item in self.items:
                    for query in item.get_drop_queries():
                        await dbt.execute_query(query=query, params={}, name="constraint_drop")

    async def list(self) -> List[ConstraintInfo]:
        if self.db.db_type == DatabaseType.NEO4J:
            return await self._list_neo4j()
        if self.db.db_type == DatabaseType.MEMGRAPH:
            return await self._list_memgraph()
        raise TypeError(f"Unsupported DatabaseType {self.db.db_type}")

    async def _list_memgraph(self) -> List[ConstraintInfo]:
        query = "SHOW CONSTRAINT INFO"
        records = await self.db.execute_query(query=query, params={}, name="constraint_show")
        results = []
        for record in records:
            results.append(ConstraintInfo(item_name="n_a", item_label=record["label"], property=record["properties"]))

        return results

    async def _list_neo4j(self) -> List[ConstraintInfo]:
        query = "SHOW CONSTRAINTS"
        records = await self.db.execute_query(query=query, params={}, name="constraint_show")
        results = []
        # breakpoint()
        for record in records:
            results.append(
                ConstraintInfo(
                    item_name=record["name"],
                    item_label=", ".join(record["labelsOrTypes"]),
                    property=", ".join(record["properties"]),
                )
            )

        return results
