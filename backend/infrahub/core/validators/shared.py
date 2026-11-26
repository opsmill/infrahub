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
        node_uuids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a query that finds the data a schema change would violate.

        Args:
            is_isolated: Whether a query on a branch reads the default branch as it was when the branch was created or
                last rebased, instead of its current data.
            node_uuids: The nodes to check, or None to check every node with the labels of the query.
            **kwargs: Forwarded to the base query.

        """
        self.node_schema = node_schema
        self.schema_path = schema_path
        self.is_isolated = is_isolated
        self.node_uuids = node_uuids
        super().__init__(**kwargs)

    def match_nodes(self, labels: str | None = None) -> str:
        """Return the MATCH clause that binds `n` to the nodes to check, and add the parameter it reads.

        Args:
            labels: The label expression the nodes must match, for example `InfraDevice|ProfileInfraDevice`; the kind of
                the schema when None.

        """
        labels = labels or self.node_schema.kind
        if self.node_uuids is None:
            return f"MATCH (n:{labels})"
        self.params["node_uuids"] = self.node_uuids
        # The uuid index is declared on the Node label, so naming it lets the read start from the listed nodes.
        return f"MATCH (n:Node WHERE n.uuid IN $node_uuids AND n:{labels})"

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
