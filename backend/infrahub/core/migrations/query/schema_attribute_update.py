from __future__ import annotations

from typing import TYPE_CHECKING, Any

import ujson

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class SchemaAttributeUpdateQuery(Query):
    name = "schema_attribute_update"
    type = QueryType.WRITE
    insert_return = True

    def __init__(
        self,
        attribute_name: str,
        node_name: str,
        node_namespace: str,
        new_value: Any,
        previous_value: Any | None = None,
        **kwargs: Any,
    ):
        self.attr_name = attribute_name
        self.node_name = node_name
        self.node_namespace = node_namespace
        self.attr_new_value = new_value
        self.attr_previous_value = previous_value

        super().__init__(**kwargs)

    def render_match(self) -> str:
        return self._render_match_schema_node()

    def _render_match_schema_node(self) -> str:
        # ruff: noqa: E501
        query = """
        MATCH path = (node:SchemaNode)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[rel:HAS_VALUE]->(av:AttributeValue)
        """
        return query

    def _render_match_schema_attribute(self) -> str:
        # ruff: noqa: E501
        query = """
        MATCH path = (node:SchemaNode)-[:IS_RELATED]->(:Relationship)<-[:IS_RELATED]-(attr_node:SchemaAttribute)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[rel:HAS_VALUE]->(av:AttributeValue)
        """
        return query

    def render_where(self) -> str:
        at = self.at or Timestamp()
        filters, params = at.get_query_filter_path()
        self.params.update(params)

        # ruff: noqa: E501
        query = """
        WHERE exists((node)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValue { value: $node_name}))
            AND exists((node)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(:AttributeValue { value: $node_namespace }))
            AND attr.name = $attr_name
            AND all(r IN relationships(path) WHERE ( %(filters)s ))
        """ % {"filters": filters}
        if self.attr_previous_value:
            query += "\n  AND av.value = $attr_previous_value"

        return query

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["attr_name"] = self.attr_name
        self.params["attr_new_value"] = (
            ujson.dumps(self.attr_new_value) if isinstance(self.attr_new_value, list) else self.attr_new_value
        )
        self.params["attr_previous_value"] = (
            ujson.dumps(self.attr_previous_value)
            if isinstance(self.attr_previous_value, list)
            else self.attr_previous_value
        )
        self.params["node_name"] = self.node_name
        self.params["node_namespace"] = self.node_namespace

        # Select the Node to update, either SchemaNode or SchemaAttribute
        self.add_to_query(self.render_match())
        self.add_to_query(self.render_where())

        query = """
        MERGE (new_value: AttributeValue { value: $attr_new_value, is_default: false })
        CREATE (attr)-[:HAS_VALUE { branch: rel.branch, branch_level: rel.branch_level, status: "active", from: $at } ]->(new_value)
        SET rel.to = $at
        """
        self.add_to_query(query)
        self.return_labels = ["attr"]
