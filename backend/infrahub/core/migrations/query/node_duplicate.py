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
    """Duplicates a Node to use a new kind or inheritance.

    Creates a copy of each affected Node and sets the new kind/inheritance.
    Adds duplicate edges to the new Node that match all the active edges on the old Node.
    Sets all the edges on the old Node to deleted.

    ``kind_updates_map`` maps each kind being migrated to the schema its vertices should end
    up with. A kind and the Profile/Template kinds generated from it are disjoint vertex
    populations that must move together, so they are migrated in a single execution.
    """

    name = "node_duplicate"
    type = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        kind_updates_map: dict[str, SchemaNodeInfo],
        **kwargs: Any,
    ) -> None:
        if not kind_updates_map:
            raise ValueError("At least one kind is required to duplicate nodes")
        self.kind_updates_map = kind_updates_map
        super().__init__(**kwargs)

    @property
    def previous_kinds(self) -> str:
        """The kinds to migrate, as a Neo4j label disjunction."""
        return "|".join(self.kind_updates_map)

    def render_match(self) -> str:
        return """
        // Find all the active nodes
        MATCH (node:%(previous_kinds)s)
        WITH DISTINCT node, $kind_map[node.kind] AS target
        // ----------------
        // Filter out nodes that have already been migrated
        // ----------------
        WHERE target IS NOT NULL
        AND NOT (
            node.kind = target.new_kind
            AND size(labels(node)) = size(target.new_all_labels)
            AND all(node_label IN labels(node) WHERE node_label IN target.new_all_labels)
        )
        """ % {"previous_kinds": self.previous_kinds}

    @staticmethod
    def _render_sub_query_per_rel_type(rel_name: str, rel_type: str, rel_dir: GraphRelDirection) -> str:
        subquery = [
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
        return "\n".join(subquery)

    @classmethod
    def _render_sub_query_out(cls) -> tuple[str, str]:
        rel_name = "rel_outband"
        sub_query_out_args = f"peer_node, {rel_name}, active_node, new_node"
        sub_queries_out = [
            cls._render_sub_query_per_rel_type(rel_name=rel_name, rel_type=rel_type, rel_dir=GraphRelDirection.OUTBOUND)
            for rel_type, field_info in GraphNodeRelationships.model_fields.items()
            if field_info.default.direction in (GraphRelDirection.OUTBOUND, GraphRelDirection.EITHER)
        ]
        sub_query_out = "\nUNION\n".join(sub_queries_out)
        return sub_query_out, sub_query_out_args

    @classmethod
    def _render_sub_query_in(cls) -> tuple[str, str]:
        rel_name = "rel_inband"
        sub_query_in_args = f"peer_node, {rel_name}, active_node, new_node"
        sub_queries_in = [
            cls._render_sub_query_per_rel_type(rel_name=rel_name, rel_type=rel_type, rel_dir=GraphRelDirection.INBOUND)
            for rel_type, field_info in GraphNodeRelationships.model_fields.items()
            if field_info.default.direction in (GraphRelDirection.INBOUND, GraphRelDirection.EITHER)
        ]
        sub_query_in = "\nUNION\n".join(sub_queries_in)
        return sub_query_in, sub_query_in_args

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["kind_map"] = {
            previous_kind: {
                "new_kind": new_node.kind,
                "new_labels": sorted(set(new_node.labels)),
                "new_namespace": new_node.namespace,
                "new_branch_support": new_node.branch_support,
                # Neo4j always adds the Node label, so it belongs in the already-migrated comparison
                "new_all_labels": sorted(set(new_node.labels) | {"Node"}),
            }
            for previous_kind, new_node in self.kind_updates_map.items()
        }

        self.params["current_time"] = self.at.to_string()
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level

        self.params["user_id"] = self.user_id

        self.params["rel_props_new"] = {
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }

        self.params["rel_props_prev"] = {
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }

        # Set metadata for vertex properties on default/global branch
        self.params["set_metadata"] = self.branch.is_default or self.branch.is_global

        sub_query_out, sub_query_out_args = self._render_sub_query_out()
        sub_query_in, sub_query_in_args = self._render_sub_query_in()

        self.add_to_query(self.render_match())

        query = """
        CALL (node) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN node as active_node, r.status = "active" AS is_active
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH target, active_node, is_active
        WHERE is_active = TRUE
        CREATE (new_node:Node:$(target.new_labels) {
            uuid: active_node.uuid, kind: target.new_kind, namespace: target.new_namespace, branch_support: target.new_branch_support
        })
        WITH active_node, new_node
        // Set metadata on new Node vertex
        CALL (active_node, new_node) {
            // always pass created_by/at from active node
            SET new_node.created_at = active_node.created_at, new_node.created_by = active_node.created_by
            WITH active_node, new_node
            // set updated_by/at if we're on the default/global branch
            WHERE $set_metadata
            SET active_node.previous_updated_at = CASE
                WHEN active_node.updated_at IS NULL OR active_node.updated_at <> $current_time THEN active_node.updated_at
                ELSE active_node.previous_updated_at
            END,
            active_node.previous_updated_by = CASE
                WHEN active_node.updated_at IS NULL OR active_node.updated_at <> $current_time THEN active_node.updated_by
                ELSE active_node.previous_updated_by
            END
            SET active_node.updated_at = $current_time, active_node.updated_by = $user_id
            // new_node is created here, so it has no prior metadata to snapshot for rollback
            SET new_node.updated_at = $current_time, new_node.updated_by = $user_id
        }

        // Process Outbound Relationship
        MATCH (active_node)-[]->(peer_node)
        WITH DISTINCT active_node, new_node, peer_node
        CALL (active_node, peer_node) {
            MATCH (active_node)-[r]->(peer_node)
            WHERE %(branch_filter)s
            RETURN r as rel_outband
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH active_node, rel_outband, peer_node, new_node
        WHERE rel_outband.status = "active" AND rel_outband.to IS NULL
        CALL (%(sub_query_out_args)s) {
            %(sub_query_out)s
        }
        WITH peer_node, rel_outband, active_node, new_node
        CALL (rel_outband) {
            WITH rel_outband
            WHERE rel_outband.branch IN ["-global-", $branch]
            SET rel_outband.to = $current_time, rel_outband.to_user_id = $user_id
        }
        WITH DISTINCT active_node, new_node
        // Process Inbound Relationship
        MATCH (active_node)<-[]-(peer_node)
        WITH DISTINCT active_node, new_node, peer_node
        CALL (active_node, peer_node) {
            MATCH (active_node)<-[r]-(peer_node)
            WHERE %(branch_filter)s
            RETURN r as rel_inband
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH active_node, rel_inband, peer_node, new_node
        WHERE rel_inband.status = "active" AND rel_inband.to IS NULL
        CALL (%(sub_query_in_args)s) {
            %(sub_query_in)s
        }
        WITH peer_node, rel_inband, active_node, new_node
        CALL (rel_inband) {
            WITH rel_inband
            WHERE rel_inband.branch IN ["-global-", $branch]
            SET rel_inband.to = $current_time, rel_inband.to_user_id = $user_id
        }
        RETURN DISTINCT new_node
        """ % {
            "branch_filter": branch_filter,
            "sub_query_out": sub_query_out,
            "sub_query_in": sub_query_in,
            "sub_query_out_args": sub_query_out_args,
            "sub_query_in_args": sub_query_in_args,
        }
        self.add_to_query(query)
