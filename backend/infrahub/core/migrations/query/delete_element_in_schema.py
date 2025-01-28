from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipStatus
from infrahub.core.graph.schema import GraphNodeRelationships, GraphRelDirection
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class DeleteElementInSchemaQuery(Query):
    name = "delete_element_in_schema"
    type = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        element_names: list[str],
        node_name: str,
        node_namespace: str,
        **kwargs: Any,
    ) -> None:
        self.element_names = element_names
        self.node_name = node_name
        self.node_namespace = node_namespace

        super().__init__(**kwargs)

    def render_match(self) -> str:
        query = """
        MATCH path = (attr_node:Node)-[:HAS_ATTRIBUTE]->(attr:Attribute)
        MATCH (attr_node)-[:HAS_ATTRIBUTE]->(attr_name:Attribute)-[:HAS_VALUE]->(attr_value:AttributeValue)
        """
        return query

    def render_where(self) -> str:
        at = self.at or Timestamp()
        filters, params = at.get_query_filter_path()
        self.params.update(params)

        # ruff: noqa: E501
        query = """
        WHERE ( "SchemaAttribute" in LABELS(attr_node) OR "SchemaRelationship" IN LABELS(attr_node))
            AND exists( (attr_node)-[:IS_RELATED]->(:Relationship)<-[:IS_RELATED]-(:Node)-[:HAS_ATTRIBUTE]->(:Attribute { name: "name"})-[:HAS_VALUE]->(:AttributeValue { value: $node_name }) )
            AND exists( (attr_node)-[:IS_RELATED]->(:Relationship)<-[:IS_RELATED]-(:Node)-[:HAS_ATTRIBUTE]->(:Attribute { name: "namespace"})-[:HAS_VALUE]->(:AttributeValue  { value: $node_namespace }) )
            AND ( attr_name.name = "name" AND attr_value.value IN $element_names)
            AND all(r IN relationships(path) WHERE ( %(filters)s ))
        """ % {"filters": filters}

        return query

    @staticmethod
    def _render_sub_query_per_rel_type(rel_name: str, rel_type: str, direction: GraphRelDirection) -> str:
        subquery = [
            f"WITH peer_node, {rel_name}, element_to_delete",
            f"WITH peer_node, {rel_name}, element_to_delete",
            f'WHERE type({rel_name}) = "{rel_type}"',
        ]
        if direction == GraphRelDirection.OUTBOUND:
            subquery.append(f"CREATE (element_to_delete)-[:{rel_type} $rel_props_prev ]->(peer_node)")
        elif direction == GraphRelDirection.INBOUND:
            subquery.append(f"CREATE (element_to_delete)<-[:{rel_type} $rel_props_prev ]-(peer_node)")
        subquery.append("RETURN peer_node as p2")
        return "\n".join(subquery)

    @classmethod
    def _render_sub_query_out(cls) -> str:
        sub_queries_out = [
            cls._render_sub_query_per_rel_type(
                rel_name="rel_outband", rel_type=rel_type, direction=GraphRelDirection.OUTBOUND
            )
            for rel_type, rel_def in GraphNodeRelationships.model_fields.items()
            if rel_def.default.direction in [GraphRelDirection.OUTBOUND, GraphRelDirection.EITHER]
        ]
        sub_query_out = "\nUNION\n".join(sub_queries_out)
        return sub_query_out

    @classmethod
    def _render_sub_query_in(cls) -> str:
        sub_queries_in = [
            cls._render_sub_query_per_rel_type(
                rel_name="rel_inband", rel_type=rel_type, direction=GraphRelDirection.INBOUND
            )
            for rel_type, rel_def in GraphNodeRelationships.model_fields.items()
            if rel_def.default.direction in [GraphRelDirection.INBOUND, GraphRelDirection.EITHER]
        ]
        sub_query_in = "\nUNION\n".join(sub_queries_in)
        return sub_query_in

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["element_names"] = self.element_names
        self.params["node_name"] = self.node_name
        self.params["node_namespace"] = self.node_namespace

        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name

        self.params["rel_props_prev"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        sub_query_out = self._render_sub_query_out()
        sub_query_in = self._render_sub_query_in()

        self.add_to_query(self.render_match())
        self.add_to_query(self.render_where())

        # ruff: noqa: E501
        query = """
        CALL {
            WITH attr_node
            MATCH (root:Root)<-[r:IS_PART_OF]-(attr_node)
            WHERE %(branch_filter)s
            RETURN attr_node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as element_to_delete, r1 as rb
        WHERE rb.status = "active"
        WITH DISTINCT(element_to_delete) as element_to_delete

        // Process Outbound Relationship
        MATCH (element_to_delete)-[]->(peer)
        CALL {
            WITH element_to_delete, peer
            MATCH (element_to_delete)-[r]->(peer)
            WHERE %(branch_filter)s
            RETURN element_to_delete as n1, r as rel_outband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as element_to_delete, rel_outband1 as rel_outband, p1 as peer_node
        WHERE rel_outband.status = "active"
        CALL {
            %(sub_query_out)s
        }
        WITH p2 as peer_node, rel_outband, element_to_delete
        FOREACH (i in CASE WHEN rel_outband.branch = $branch_name THEN [1] ELSE [] END |
            SET rel_outband.to = $current_time
        )
        WITH DISTINCT(element_to_delete) AS element_to_delete
        // Process Inbound Relationship
        MATCH (element_to_delete)<-[]-(peer)
        CALL {
            WITH element_to_delete, peer
            MATCH (element_to_delete)<-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN element_to_delete as n1, r as rel_inband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as element_to_delete, rel_inband1 as rel_inband, p1 as peer_node
        WHERE rel_inband.status = "active"
        CALL {
            %(sub_query_in)s
        }
        WITH p2 as peer_node, rel_inband, element_to_delete
        FOREACH (i in CASE WHEN rel_inband.branch = $branch_name THEN [1] ELSE [] END |
            SET rel_inband.to = $current_time
        )
        RETURN DISTINCT element_to_delete
        """ % {
            "branch_filter": branch_filter,
            "sub_query_out": sub_query_out,
            "sub_query_in": sub_query_in,
        }
        self.add_to_query(query)
