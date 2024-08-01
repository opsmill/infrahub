from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType  # noqa: TCH001
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class SchemaAttributeUpdateQuery(Query):
    name = "schema_attribute_update"
    type: QueryType = QueryType.WRITE
    insert_return = True

    def __init__(
        self,
        attribute_name: str,
        node_name: str,
        node_namespace: str,
        previous_value: Any,
        new_value: Any,
        **kwargs: Any,
    ):
        self.attr_name = attribute_name
        self.node_name = node_name
        self.node_namespace = node_namespace
        self.attr_new_value = new_value
        self.attr_previous_value = previous_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        at = self.at or Timestamp()
        filters, params = at.get_query_filter_path()
        self.params.update(params)

        self.params["attr_name"] = self.attr_name
        self.params["attr_new_value"] = self.attr_new_value
        self.params["attr_previous_value"] = self.attr_previous_value
        self.params["node_name"] = self.node_name
        self.params["node_namespace"] = self.node_namespace

        # ruff: noqa: E501
        query = """
        MATCH path = (node:SchemaNode)-[:IS_RELATED]->(:Relationship)<-[:IS_RELATED]-(attr_node:SchemaAttribute)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[rel:HAS_VALUE]->(av:AttributeValue)
        WHERE (node)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValue { value: $node_name})
            AND (node)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(:AttributeValue { value: $node_namespace })
            AND attr.name = $attr_name
            AND av.value = $attr_previous_value
            AND all(r IN relationships(path) WHERE ( %(filters)s ))
        MERGE (new_value: AttributeValue { value: $attr_new_value, is_default: false })
        CREATE (attr)-[:HAS_VALUE { branch: rel.branch, branch_level: rel.branch_level, status: "active", from: $at, to: null } ]->(new_value)
        SET rel.to = $at
        """ % {"filters": filters}
        self.add_to_query(query)
        self.return_labels = ["attr"]
