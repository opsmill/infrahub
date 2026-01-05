from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from infrahub.core.constants import BranchSupportType, RelationshipStatus
from infrahub.core.graph.schema import GraphRelationshipRelationships, GraphRelDirection
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class SchemaRelationshipInfo(BaseModel):
    name: str
    branch_support: str = BranchSupportType.AWARE.value
    src_peer: str
    dst_peer: str


class RelationshipDuplicateQuery(Query):
    name = "relationship_duplicate"
    type = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        previous_rel: SchemaRelationshipInfo,
        new_rel: SchemaRelationshipInfo,
        **kwargs: Any,
    ) -> None:
        self.previous_rel = previous_rel
        self.new_rel = new_rel

        super().__init__(**kwargs)

    def render_match(self) -> str:
        query = """
        // Find all the active nodes
        MATCH (source:%(src_peer)s)-[:IS_RELATED]-(rel:Relationship { name: $previous_rel.name })-[:IS_RELATED]-(destination:%(dst_peer)s)
        WHERE source <> destination
        """ % {"src_peer": self.previous_rel.src_peer, "dst_peer": self.previous_rel.dst_peer}

        return query

    @staticmethod
    def _render_sub_query_per_rel_type(rel_name: str, rel_type: str, direction: GraphRelDirection) -> str:
        subquery = [
            f"WITH peer_node, {rel_name}, active_rel, new_rel",
            f'WHERE type({rel_name}) = "{rel_type}"',
        ]
        if direction == GraphRelDirection.OUTBOUND:
            subquery.append(f"CREATE (new_rel)-[:{rel_type} $rel_props_new ]->(peer_node)")
            subquery.append(f"CREATE (active_rel)-[:{rel_type} $rel_props_prev ]->(peer_node)")
        elif direction == GraphRelDirection.INBOUND:
            subquery.append(f"CREATE (new_rel)<-[:{rel_type} $rel_props_new ]-(peer_node)")
            subquery.append(f"CREATE (active_rel)<-[:{rel_type} $rel_props_prev ]-(peer_node)")
        subquery.append("RETURN peer_node as p2")
        return "\n".join(subquery)

    @classmethod
    def _render_sub_query_out(cls) -> tuple[str, str]:
        rel_name = "rel_outband"
        sub_query_out_args = f"peer_node, {rel_name}, active_rel, new_rel"
        sub_queries_out = [
            cls._render_sub_query_per_rel_type(
                rel_name=rel_name, rel_type=rel_type, direction=GraphRelDirection.OUTBOUND
            )
            for rel_type, rel_def in GraphRelationshipRelationships.model_fields.items()
            if rel_def.default.direction in [GraphRelDirection.OUTBOUND, GraphRelDirection.EITHER]
        ]
        sub_query_out = "\nUNION\n".join(sub_queries_out)
        return sub_query_out, sub_query_out_args

    @classmethod
    def _render_sub_query_in(cls) -> tuple[str, str]:
        rel_name = "rel_inband"
        sub_query_in_args = f"peer_node, {rel_name}, active_rel, new_rel"
        sub_queries_in = [
            cls._render_sub_query_per_rel_type(
                rel_name=rel_name, rel_type=rel_type, direction=GraphRelDirection.INBOUND
            )
            for rel_type, rel_def in GraphRelationshipRelationships.model_fields.items()
            if rel_def.default.direction in [GraphRelDirection.INBOUND, GraphRelDirection.EITHER]
        ]
        sub_query_in = "\nUNION\n".join(sub_queries_in)
        return sub_query_in, sub_query_in_args

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["new_rel"] = self.new_rel.model_dump()
        self.params["previous_rel"] = self.previous_rel.model_dump()

        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name
        self.params["branch_support"] = self.new_rel.branch_support

        self.params["rel_props_new"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
        }

        self.params["rel_props_prev"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        sub_query_out, sub_query_out_args = self._render_sub_query_out()
        sub_query_in, sub_query_in_args = self._render_sub_query_in()

        self.add_to_query(self.render_match())

        query = """
        CALL (source, rel, destination) {
            MATCH path = (source)-[r1:IS_RELATED]-(rel)-[r2:IS_RELATED]-(destination)
            WHERE all(r IN relationships(path) WHERE %(branch_filter)s)
            RETURN rel as rel1, r1 as r11, r2 as r12
            ORDER BY r1.branch_level DESC, r2.branch_level DESC, r1.from DESC, r2.from DESC
            LIMIT 1
        }
        WITH rel1 as active_rel, r11 as r1, r12 as r2
        WHERE r1.status = "active" AND r2.status = "active"
        CREATE (new_rel:Relationship { uuid: active_rel.uuid, name: $new_rel.name, branch_support: $new_rel.branch_support })
        WITH DISTINCT(active_rel) as active_rel, new_rel
        // Process Inbound Relationship
        MATCH (active_rel)<-[]-(peer)
        CALL (active_rel, peer) {
            MATCH (active_rel)<-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN active_rel as n1, r as rel_inband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_rel, rel_inband1 as rel_inband, p1 as peer_node, new_rel
        WHERE rel_inband.status = "active"
        CALL (%(sub_query_in_args)s) {
            %(sub_query_in)s
        }
        WITH p2 as peer_node, rel_inband, active_rel, new_rel
        FOREACH (i in CASE WHEN rel_inband.branch = $branch_name THEN [1] ELSE [] END |
            SET rel_inband.to = $current_time
        )
        WITH DISTINCT(active_rel) as active_rel, new_rel
        // Process Outbound Relationship
        MATCH (active_rel)-[]->(peer)
        CALL (active_rel, peer) {
            MATCH (active_rel)-[r]->(peer)
            WHERE %(branch_filter)s
            RETURN active_rel as n1, r as rel_outband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_rel, rel_outband1 as rel_outband, p1 as peer_node, new_rel
        WHERE rel_outband.status = "active"
        CALL (%(sub_query_out_args)s) {
            %(sub_query_out)s
        }
        WITH p2 as peer_node, rel_outband, active_rel, new_rel
        FOREACH (i in CASE WHEN rel_outband.branch = $branch_name THEN [1] ELSE [] END |
            SET rel_outband.to = $current_time
        )
        RETURN DISTINCT new_rel
        """ % {
            "branch_filter": branch_filter,
            "sub_query_out": sub_query_out,
            "sub_query_in": sub_query_in,
            "sub_query_in_args": sub_query_in_args,
            "sub_query_out_args": sub_query_out_args,
        }
        self.add_to_query(query)
