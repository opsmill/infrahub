from __future__ import annotations

from typing import Any

from infrahub.core.path import GroupedDataPaths, SchemaPath  # noqa: TC001
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema  # noqa: TC001


class SchemaValidatorQuery(Query):
    type: QueryType = QueryType.READ

    def __init__(
        self,
        node_schema: NodeSchema | GenericSchema,
        schema_path: SchemaPath,
        node_uuids: set[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.node_schema = node_schema
        self.schema_path = schema_path
        # Optional scope for data-diff-driven constraint runs. Subclasses that
        # opt in stamp this on $node_uuids and gate their initial MATCH with
        # `WHERE $node_uuids IS NULL OR n.uuid IN $node_uuids`, falling back to
        # a full kind scan when None (the schema-diff-origin case).
        self.node_uuids: list[str] | None = list(node_uuids) if node_uuids else None
        super().__init__(**kwargs)

    async def get_paths(self) -> GroupedDataPaths:
        raise NotImplementedError()


class AttributeSchemaValidatorQuery(SchemaValidatorQuery):
    @property
    def attribute_schema(self) -> AttributeSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name not defined")
        return self.node_schema.get_attribute(name=self.schema_path.field_name)


class RelationshipSchemaValidatorQuery(SchemaValidatorQuery):
    @property
    def relationship_schema(self) -> RelationshipSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name not defined")
        return self.node_schema.get_relationship(name=self.schema_path.field_name)
