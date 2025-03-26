from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from infrahub.core.constants import BranchSupportType, RelationshipStatus
from infrahub.core.graph.schema import GraphNodeRelationships, GraphRelDirection
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class SchemaNodeInfo(BaseModel):
    name: str
    namespace: str
    branch_support: str = BranchSupportType.AWARE.value
    labels: list[str]
    kind: str


class NodeDuplicateQuery(Query):
    name = "node_duplicate"
    type = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        previous_node: SchemaNodeInfo,
        new_node: SchemaNodeInfo,
        **kwargs: Any,
    ) -> None:
        self.previous_node = previous_node
        self.new_node = new_node

        super().__init__(**kwargs)

    def render_match(self) -> str:
        query = f"""
        // Find all the active nodes
        MATCH (node:{self.previous_node.kind})
        """

        return query

    @staticmethod
    def _render_sub_query_per_rel_type(rel_name: str, rel_type: str, rel_dir: GraphRelDirection) -> str:
        subquery = [
            f"WITH peer_node, {rel_name}, active_node, new_node",
            f"WITH peer_node, {rel_name}, active_node, new_node",
            f'WHERE type({rel_name}) = "{rel_type}"',
        ]
        if rel_dir in [GraphRelDirection.OUTBOUND, GraphRelDirection.EITHER]:
            subquery.append(f"""
                CREATE (new_node)-[new_active_edge:{rel_type} $rel_props_new ]->(peer_node)
                SET new_active_edge.branch = CASE WHEN {rel_name}.branch = "-global-" THEN "-global-" ELSE $branch END
                SET new_active_edge.branch_level = CASE WHEN {rel_name}.branch = "-global-" THEN {rel_name}.branch_level ELSE $branch_level END
                SET new_active_edge.hierarchy = COALESCE({rel_name}.hierarchy, NULL)
                """)
            subquery.append(f"""
                CREATE (active_node)-[deleted_edge:{rel_type} $rel_props_prev ]->(peer_node)
                SET deleted_edge.branch = CASE WHEN {rel_name}.branch = "-global-" THEN "-global-" ELSE $branch END
                SET deleted_edge.branch_level = CASE WHEN {rel_name}.branch = "-global-" THEN {rel_name}.branch_level ELSE $branch_level END
                SET deleted_edge.hierarchy = COALESCE({rel_name}.hierarchy, NULL)
                """)
        elif rel_dir in [GraphRelDirection.INBOUND, GraphRelDirection.EITHER]:
            subquery.append(f"""
                CREATE (new_node)<-[new_active_edge:{rel_type} $rel_props_new ]-(peer_node)
                SET new_active_edge.branch = CASE WHEN {rel_name}.branch = "-global-" THEN "-global-" ELSE $branch END
                SET new_active_edge.branch_level = CASE WHEN {rel_name}.branch = "-global-" THEN {rel_name}.branch_level ELSE $branch_level END
                SET new_active_edge.hierarchy = COALESCE({rel_name}.hierarchy, NULL)
                """)
            subquery.append(f"""
                CREATE (active_node)<-[deleted_edge:{rel_type} $rel_props_prev ]-(peer_node)
                SET deleted_edge.branch = CASE WHEN {rel_name}.branch = "-global-" THEN "-global-" ELSE $branch END
                SET deleted_edge.branch_level = CASE WHEN {rel_name}.branch = "-global-" THEN {rel_name}.branch_level ELSE $branch_level END
                SET deleted_edge.hierarchy = COALESCE({rel_name}.hierarchy, NULL)
                """)
        subquery.append("RETURN peer_node as p2")
        return "\n".join(subquery)

    @classmethod
    def _render_sub_query_out(cls) -> str:
        sub_queries_out = [
            cls._render_sub_query_per_rel_type(
                rel_name="rel_outband", rel_type=rel_type, rel_dir=GraphRelDirection.OUTBOUND
            )
            for rel_type, field_info in GraphNodeRelationships.model_fields.items()
            if field_info.default.direction in (GraphRelDirection.OUTBOUND, GraphRelDirection.EITHER)
        ]
        sub_query_out = "\nUNION\n".join(sub_queries_out)
        return sub_query_out

    @classmethod
    def _render_sub_query_in(cls) -> str:
        sub_queries_in = [
            cls._render_sub_query_per_rel_type(
                rel_name="rel_inband", rel_type=rel_type, rel_dir=GraphRelDirection.INBOUND
            )
            for rel_type, field_info in GraphNodeRelationships.model_fields.items()
            if field_info.default.direction in (GraphRelDirection.INBOUND, GraphRelDirection.EITHER)
        ]
        sub_query_in = "\nUNION\n".join(sub_queries_in)
        return sub_query_in

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["new_node"] = self.new_node.model_dump()
        self.params["previous_node"] = self.previous_node.model_dump()

        self.params["current_time"] = self.at.to_string()
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["branch_support"] = self.new_node.branch_support

        self.params["rel_props_new"] = {
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
        }

        self.params["rel_props_prev"] = {
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        sub_query_out = self._render_sub_query_out()
        sub_query_in = self._render_sub_query_in()

        self.add_to_query(self.render_match())

        # ruff: noqa: E501
        query = """
        CALL {
            WITH node
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb
        WHERE rb.status = "active"
        CREATE (new_node:Node:%(labels)s { uuid: active_node.uuid, kind: $new_node.kind, namespace: $new_node.namespace, branch_support: $new_node.branch_support })
        WITH active_node, new_node
        // Process Outbound Relationship
        MATCH (active_node)-[]->(peer)
        CALL {
            WITH active_node, peer
            MATCH (active_node)-[r]->(peer)
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as rel_outband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, rel_outband1 as rel_outband, p1 as peer_node, new_node
        WHERE rel_outband.status = "active" AND rel_outband.to IS NULL
        CALL {
            %(sub_query_out)s
        }
        WITH p2 as peer_node, rel_outband, active_node, new_node
        FOREACH (i in CASE WHEN rel_outband.branch IN ["-global-", $branch] THEN [1] ELSE [] END |
            SET rel_outband.to = $current_time
        )
        WITH DISTINCT active_node, new_node
        // Process Inbound Relationship
        MATCH (active_node)<-[]-(peer)
        CALL {
            WITH active_node, peer
            MATCH (active_node)<-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as rel_inband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, rel_inband1 as rel_inband, p1 as peer_node, new_node
        WHERE rel_inband.status = "active" AND rel_inband.to IS NULL
        CALL {
            %(sub_query_in)s
        }
        WITH p2 as peer_node, rel_inband, active_node, new_node
        FOREACH (i in CASE WHEN rel_inband.branch IN ["-global-", $branch] THEN [1] ELSE [] END |
            SET rel_inband.to = $current_time
        )

        RETURN DISTINCT new_node
        """ % {
            "branch_filter": branch_filter,
            "labels": ":".join(self.new_node.labels),
            "sub_query_out": sub_query_out,
            "sub_query_in": sub_query_in,
        }
        self.add_to_query(query)
