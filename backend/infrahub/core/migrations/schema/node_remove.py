from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import RelationshipStatus
from infrahub.core.graph.schema import GraphNodeRelationships, GraphRelDirection

from ..shared import MigrationQuery, SchemaMigration

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.database import InfrahubDatabase


class NodeRemoveMigrationBaseQuery(MigrationQuery):
    def render_sub_query_per_rel_type(
        self,
        rel_name: str,
        rel_type: str,
        rel_def: FieldInfo,
    ) -> str:
        subquery = [
            f"WITH peer_node, {rel_name}, active_node",
            f'WHERE type({rel_name}) = "{rel_type}"',
        ]
        if rel_def.default.direction in [GraphRelDirection.OUTBOUND, GraphRelDirection.EITHER]:
            subquery.append(f"""
                CREATE (active_node)-[edge:{rel_type} $rel_props ]->(peer_node)
                SET edge.branch = CASE WHEN {rel_name}.branch = "-global-" THEN "-global-" ELSE $branch END
                SET edge.branch_level = CASE WHEN {rel_name}.branch = "-global-" THEN {rel_name}.branch_level ELSE $branch_level END
                """)
        elif rel_def.default.direction in [GraphRelDirection.INBOUND, GraphRelDirection.EITHER]:
            subquery.append(f"""
                CREATE (active_node)<-[edge:{rel_type} $rel_props ]-(peer_node)
                SET edge.branch = CASE WHEN {rel_name}.branch = "-global-" THEN "-global-" ELSE $branch END
                SET edge.branch_level = CASE WHEN {rel_name}.branch = "-global-" THEN {rel_name}.branch_level ELSE $branch_level END
                """)
        subquery.append("RETURN peer_node as p2")
        return "\n".join(subquery)

    def render_node_remove_query(self, branch_filter: str) -> str:
        raise NotImplementedError()

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level

        self.params["rel_props"] = {
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        node_remove_query = self.render_node_remove_query(branch_filter=branch_filter)

        query = """
        // Find all the active nodes
        MATCH (node:%(node_kind)s)
        CALL (node) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb
        WHERE rb.status = "active"
        %(node_remove_query)s
        RETURN DISTINCT active_node
        """ % {
            "branch_filter": branch_filter,
            "node_remove_query": node_remove_query,
            "node_kind": self.migration.previous_schema.kind,
        }
        self.add_to_query(query)

    def get_nbr_migrations_executed(self) -> int:
        return self.stats.get_counter(name="nodes_created")


class NodeRemoveMigrationQueryIn(NodeRemoveMigrationBaseQuery):
    name = "migration_node_remove_in"
    insert_return: bool = False

    def render_node_remove_query(self, branch_filter: str) -> str:
        sub_query, sub_query_args = self.render_sub_query_in()
        query = """
        // Process Inbound Relationship
        WITH active_node
        MATCH (active_node)<-[]-(peer)
        CALL (active_node, peer) {
            MATCH (active_node)-[r]->(peer)
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as rel_inband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, rel_inband1 as rel_inband, p1 as peer_node
        WHERE rel_inband.status = "active"
        CALL (%(sub_query_args)s) {
            %(sub_query)s
        }
        WITH p2 as peer_node, rel_inband, active_node
        FOREACH (i in CASE WHEN rel_inband.branch IN ["-global-", $branch] THEN [1] ELSE [] END |
            SET rel_inband.to = $current_time
        )
        """ % {"sub_query": sub_query, "sub_query_args": sub_query_args, "branch_filter": branch_filter}
        return query

    def render_sub_query_in(self) -> tuple[str, str]:
        rel_name = "rel_inband"
        sub_query_in_args = f"peer_node, {rel_name}, active_node"
        sub_queries_in = [
            self.render_sub_query_per_rel_type(
                rel_name=rel_name,
                rel_type=rel_type,
                rel_def=rel_def,
            )
            for rel_type, rel_def in GraphNodeRelationships.model_fields.items()
        ]
        sub_query_in = "\nUNION\n".join(sub_queries_in)
        return sub_query_in, sub_query_in_args

    def get_nbr_migrations_executed(self) -> int:
        return 0


class NodeRemoveMigrationQueryOut(NodeRemoveMigrationBaseQuery):
    name = "migration_node_remove_in"
    insert_return: bool = False

    def render_node_remove_query(self, branch_filter: str) -> str:
        sub_query, sub_query_args = self.render_sub_query_out()
        query = """
        // Process Outbound Relationship
        WITH active_node
        MATCH (active_node)-[]->(peer)
        CALL (active_node, peer) {
            MATCH (active_node)-[r]->(peer)
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as rel_outband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, rel_outband1 as rel_outband, p1 as peer_node
        WHERE rel_outband.status = "active"
        CALL (%(sub_query_args)s) {
            %(sub_query)s
        }
        FOREACH (i in CASE WHEN rel_outband.branch IN ["-global-", $branch] THEN [1] ELSE [] END |
            SET rel_outband.to = $current_time
        )
        """ % {"sub_query": sub_query, "sub_query_args": sub_query_args, "branch_filter": branch_filter}

        return query

    def render_sub_query_out(self) -> tuple[str, str]:
        rel_name = "rel_outband"
        sub_query_out_args = f"peer_node, {rel_name}, active_node"
        sub_queries_out = [
            self.render_sub_query_per_rel_type(
                rel_name=rel_name,
                rel_type=rel_type,
                rel_def=rel_def,
            )
            for rel_type, rel_def in GraphNodeRelationships.model_fields.items()
        ]
        sub_query_out = "\nUNION\n".join(sub_queries_out)
        return sub_query_out, sub_query_out_args

    def get_nbr_migrations_executed(self) -> int:
        return self.num_of_results


class NodeRemoveMigration(SchemaMigration):
    name: str = "node.remove"
    queries: Sequence[type[MigrationQuery]] = [NodeRemoveMigrationQueryIn, NodeRemoveMigrationQueryOut]  # type: ignore[assignment]
