from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, ForwardRef, Optional, Union, get_origin

from pydantic import BaseModel
from typing_extensions import Self

from infrahub.core.query import QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


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

    def get_add_queries(self) -> list[str]:
        raise NotImplementedError()

    def get_drop_queries(self) -> list[str]:
        raise NotImplementedError()


class ConstraintItemNeo4j(ConstraintItem):
    def names(self) -> list[str]:
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

    def get_add_queries(self) -> list[str]:
        queries = [self.get_query_main_add()]
        if self.mandatory:
            queries.append(self.get_query_exist_add())
        return queries

    def get_drop_queries(self) -> list[str]:
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

    def get_add_queries(self) -> list[str]:
        return [self.get_query_exist_add()]

    def get_drop_queries(self) -> list[str]:
        return [self.get_query_exist_drop()]


class ConstraintNodeMemgraph(ConstraintItemMemgraph):
    def get_query_exist_add(self) -> str:
        return f"CREATE CONSTRAINT ON (n:{self.item_label}) ASSERT EXISTS (n.{self.property})"

    def get_query_exist_drop(self) -> str:
        return f"DROP CONSTRAINT ON (n:{self.item_label}) ASSERT EXISTS (n.{self.property})"


TYPE_MAPPING = {
    "RelationshipStatus": GraphPropertyType.STRING,
    "BranchSupportType": GraphPropertyType.STRING,
    str: GraphPropertyType.STRING,
    int: GraphPropertyType.INTEGER,
    bool: GraphPropertyType.BOOLEAN,
    float: GraphPropertyType.FLOAT,
}


class ConstraintManagerBase:
    constraint_node_class: Optional[type[ConstraintItem]] = ConstraintItem
    constraint_rel_class: Optional[type[ConstraintItem]] = ConstraintItem

    def __init__(self, db: InfrahubDatabase):
        self.db = db

        self.nodes: list[ConstraintItem] = []
        self.rels: list[ConstraintItem] = []

    @property
    def items(self) -> list[ConstraintItem]:
        return self.nodes + self.rels

    @classmethod
    def from_graph_schema(cls, db: InfrahubDatabase, schema: dict[str, dict[str, BaseModel]]) -> Self:
        manager = cls(db=db)

        # Process the nodes first
        for schema_item in schema["nodes"].values():
            properties_class: BaseModel = schema_item.model_fields["properties"].annotation  # type: ignore[assignment]
            default_label = str(schema_item.model_fields["default_label"].default)
            for field_name, field in properties_class.model_fields.items():
                clean_field_name = field.alias or field_name
                item_type = None
                mandatory = True
                if isinstance(field.annotation, ForwardRef) and field.annotation.__forward_arg__ in TYPE_MAPPING:
                    item_type = TYPE_MAPPING[field.annotation.__forward_arg__]
                elif field.annotation in TYPE_MAPPING:
                    item_type = TYPE_MAPPING[field.annotation]
                elif get_origin(field.annotation) == Union and field.annotation.__args__[0] in TYPE_MAPPING:  # type: ignore[union-attr]
                    item_type = TYPE_MAPPING[field.annotation.__args__[0]]  # type: ignore[union-attr]
                    mandatory = False
                if not item_type or not manager.constraint_node_class:
                    continue

                manager.nodes.append(
                    manager.constraint_node_class(
                        item_name=default_label.lower(),
                        item_label=default_label,
                        property=clean_field_name,
                        type=item_type,
                        mandatory=mandatory,
                    )
                )

        # Process the relationships
        for label, schema_item in schema["relationships"].items():
            for field_name, field in schema_item.model_fields.items():
                clean_field_name = field.alias or field_name
                item_type = None
                mandatory = True
                if isinstance(field.annotation, ForwardRef) and field.annotation.__forward_arg__ in TYPE_MAPPING:
                    item_type = TYPE_MAPPING[field.annotation.__forward_arg__]
                elif field.annotation in TYPE_MAPPING:
                    item_type = TYPE_MAPPING[field.annotation]
                elif get_origin(field.annotation) == Union and field.annotation.__args__[0] in TYPE_MAPPING:  # type: ignore[union-attr]
                    item_type = TYPE_MAPPING[field.annotation.__args__[0]]  # type: ignore[union-attr]
                    mandatory = False
                if not item_type or not manager.constraint_rel_class:
                    continue

                manager.rels.append(
                    manager.constraint_rel_class(
                        item_name=label.lower(),
                        item_label=label,
                        property=clean_field_name,
                        type=item_type,
                        mandatory=mandatory,
                    )
                )

        return manager

    async def add(self) -> None:
        async with self.db.start_transaction() as dbt:
            for item in self.items:
                for query in item.get_add_queries():
                    await dbt.execute_query(query=query, params={}, name="constraint_add")

    async def drop(self) -> None:
        async with self.db.start_transaction() as dbt:
            for item in self.items:
                for query in item.get_drop_queries():
                    await dbt.execute_query(query=query, params={}, name="constraint_drop")

    async def list(self) -> list[ConstraintInfo]:
        raise NotImplementedError()


class ConstraintManagerNeo4j(ConstraintManagerBase):
    constraint_node_class = ConstraintNodeNeo4j
    constraint_rel_class = ConstraintRelNeo4j

    async def list(self) -> list[ConstraintInfo]:
        query = "SHOW CONSTRAINTS"
        records = await self.db.execute_query(query=query, params={}, name="constraint_show", type=QueryType.READ)
        results = []
        for record in records:
            results.append(
                ConstraintInfo(
                    item_name=record["name"],
                    item_label=", ".join(record["labelsOrTypes"]),
                    property=", ".join(record["properties"]),
                )
            )

        return results


class ConstraintManagerMemgraph(ConstraintManagerBase):
    constraint_node_class = ConstraintNodeMemgraph
    constraint_rel_class = None

    async def add(self) -> None:
        for item in self.items:
            for query in item.get_add_queries():
                await self.db.execute_query(query=query, params={}, name="constraint_add")

    async def drop(self) -> None:
        for item in self.items:
            for query in item.get_drop_queries():
                await self.db.execute_query(query=query, params={}, name="constraint_drop")

    async def list(self) -> list[ConstraintInfo]:
        query = "SHOW CONSTRAINT INFO"
        records = await self.db.execute_query(query=query, params={}, name="constraint_show", type=QueryType.READ)
        results = []
        for record in records:
            results.append(ConstraintInfo(item_name="n_a", item_label=record["label"], property=record["properties"]))

        return results
