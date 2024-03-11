from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Sequence

from infrahub.core.constants import BranchSupportType, RelationshipStatus
from infrahub.core.graph.schema import GraphNodeRelationships, GraphRelDirection

from ..shared import MigrationQuery, SchemaMigration

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.database import InfrahubDatabase


class NodeKindUpdateMigrationQuery01(MigrationQuery):
    name = "migration_node_kind_update_01"
    insert_return: bool = False

    def render_sub_query_per_rel_type(
        self, rel_name: str, rel_type: str, rel_def: FieldInfo, direction: GraphRelDirection
    ) -> str:
        subquery = [
            f"WITH peer_node, {rel_name}, active_node, new_node",
            f"WITH peer_node, {rel_name}, active_node, new_node",
            f'WHERE type({rel_name}) = "{rel_type}"',
        ]
        if rel_def.default.direction in [direction, GraphRelDirection.EITHER]:
            subquery.append(f"CREATE (new_node)-[:{rel_type} $rel_props_new ]->(peer_node)")
            subquery.append(f"CREATE (active_node)-[:{rel_type} $rel_props_prev ]->(peer_node)")
        elif rel_def.default.direction in [direction, GraphRelDirection.EITHER]:
            subquery.append(f"CREATE (new_node)<-[:{rel_type} $rel_props_new ]-(peer_node)")
            subquery.append(f"CREATE (active_node)<-[:{rel_type} $rel_props_prev ]-(peer_node)")
        subquery.append("RETURN peer_node as p2")
        return "\n".join(subquery)

    def render_sub_query_out(self) -> str:
        sub_queries_out = [
            self.render_sub_query_per_rel_type(
                rel_name="rel_outband", rel_type=rel_type, rel_def=rel_def, direction=GraphRelDirection.OUTBOUND
            )
            for rel_type, rel_def in GraphNodeRelationships.model_fields.items()
        ]
        sub_query_out = "\nUNION\n".join(sub_queries_out)
        return sub_query_out

    def render_sub_query_in(self) -> str:
        sub_queries_in = [
            self.render_sub_query_per_rel_type(
                rel_name="rel_inband", rel_type=rel_type, rel_def=rel_def, direction=GraphRelDirection.INBOUND
            )
            for rel_type, rel_def in GraphNodeRelationships.model_fields.items()
        ]
        sub_query_in = "\nUNION\n".join(sub_queries_in)
        return sub_query_in

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["new_node_kind"] = self.migration.new_schema.kind
        self.params["new_node_namespace"] = self.migration.new_schema.namespace
        self.params["prev_node_kind"] = self.migration.previous_schema.kind
        self.params["prev_node_namespace"] = self.migration.previous_schema.namespace

        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name

        if self.branch.is_default:
            self.params["branch_support"] = self.migration.new_schema.branch.value
        else:
            self.params["branch_support"] = BranchSupportType.LOCAL.value

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

        sub_query_out = self.render_sub_query_out()
        sub_query_in = self.render_sub_query_in()

        # ruff: noqa: E501
        query = """
        // Find all the active nodes
        MATCH (node:Node)
        WHERE $prev_node_kind IN LABELS(node)
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
        CREATE (new_node:Node:%(labels)s { uuid: active_node.uuid, kind: $new_node_kind, namespace: $new_node_namespace, branch_support: $branch_support })
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
        WHERE rel_outband.status = "active"
        CALL {
            %(sub_query_out)s
        }
        WITH p2 as peer_node, rel_outband, active_node, new_node
        FOREACH (i in CASE WHEN rel_outband.branch = $branch_name THEN [1] ELSE [] END |
            SET rel_outband.to = $current_time
        )
        WITH active_node, new_node
        MATCH (active_node)<-[]-(peer)
        CALL {
            WITH active_node, peer
            MATCH (active_node)-[r]->(peer)
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as rel_inband1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, rel_inband1 as rel_inband, p1 as peer_node, new_node
        WHERE rel_inband.status = "active"
        CALL {
            %(sub_query_in)s
        }
        WITH p2 as peer_node, rel_inband, active_node, new_node
        FOREACH (i in CASE WHEN rel_inband.branch = $branch_name THEN [1] ELSE [] END |
            SET rel_inband.to = $current_time
        )
        RETURN DISTINCT new_node
        """ % {
            "branch_filter": branch_filter,
            "labels": ":".join(self.migration.new_schema.get_labels()),
            "sub_query_out": sub_query_out,
            "sub_query_in": sub_query_in,
        }
        self.add_to_query(query)

    def get_nbr_migrations_executed(self) -> int:
        return self.stats.get_counter(name="nodes_created")


class NodeKindUpdateMigration(SchemaMigration):
    name: str = "node.kind.update"
    queries: Sequence[type[MigrationQuery]] = [NodeKindUpdateMigrationQuery01]  # type: ignore[assignment]
