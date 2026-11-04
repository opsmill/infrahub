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
        is_isolated: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize a query that finds the data a schema change would violate.

        Args:
            is_isolated: Whether a query on a branch reads the default branch as it was when the branch was created or
                last rebased, instead of its current data.
            **kwargs: Forwarded to the base query.

        """
        self.node_schema = node_schema
        self.schema_path = schema_path
        self.is_isolated = is_isolated
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
