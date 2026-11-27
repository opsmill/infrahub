from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING, Any, ClassVar

from infrahub.core.constants import GLOBAL_BRANCH_NAME, RelationshipStatus
from infrahub.core.migrations.schema.phases import MigrationPhase
from infrahub.core.query.vertex_metadata import stamp_vertex_metadata

from ..query import MigrationQuery
from ..shared import SchemaMigration

if TYPE_CHECKING:
    from infrahub.core.path import SchemaPath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class NodeRemoveMigrationBaseQuery(MigrationQuery):
    """Shared parameter setup for node-remove migrations."""

    def _branch_from_existing(self, existing: str) -> str:
        """Return a Cypher fragment that computes (new_branch, new_branch_level) for a new.

        "deleted" edge based on an existing edge variable. Agnostic edges stay on the global
        branch; all others go on the migration branch.

        """
        return (
            f"CASE WHEN {existing}.branch = $global_branch THEN $global_branch ELSE $branch END AS new_branch, "
            f"CASE WHEN {existing}.branch = $global_branch "
            f"THEN {existing}.branch_level ELSE $branch_level END AS new_branch_level"
        )

    def _build_params(self) -> dict[str, Any]:
        """Return shared Cypher parameters for node-remove migration queries."""
        return {
            "current_time": self.at.to_string(),
            "branch_name": self.branch.name,
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "user_id": self.user_id,
            "global_branch": GLOBAL_BRANCH_NAME,
            "rel_props": {
                "status": RelationshipStatus.DELETED.value,
                "from": self.at.to_string(),
                "from_user_id": self.user_id,
            },
            # Set metadata for vertex properties on default/global branch
            "set_metadata": self.branch.is_default or self.branch.is_global,
        }

    def render_selection(self) -> str:
        branch_filter, _ = self.branch.get_query_filter_path(at=self.at.to_string())
        return """
    // ----------------------------------------------------------
    // Find all active nodes of the kind being removed
    // ----------------------------------------------------------
    %(node_match)s
    CALL (node) {
        MATCH (root:Root)<-[r:IS_PART_OF]-(node)
        WHERE %(branch_filter)s
        RETURN r AS root_edge
        ORDER BY r.branch_level DESC, r.from DESC
        LIMIT 1
    }
    WITH node AS active_node, root_edge
    WHERE root_edge.status = "active"
    """ % {
            "node_match": self.render_node_match("node", [self.migration.previous_schema.kind]),
            "branch_filter": branch_filter,
        }

    def get_nbr_migrations_executed(self) -> int:
        return self.stats.get_counter(name="nodes_created")


class NodeRemoveMigrationQueryIn(NodeRemoveMigrationBaseQuery):
    """Close inbound edges that point to nodes of the removed kind.

    Inbound edge types from another Node/Attribute/Relationship/OwnerSet to our active_node:
      - HAS_SOURCE        (Relationship -> Node)               : peer is the link with the source
      - HAS_OWNER         (Relationship -> Node)               : peer is the link with the owner
      - HAS_OWNER_SOURCE  (Attribute|Node|OwnerSet -> Node)    : peer is the vertex with the owners
      - IS_RELATED        (Node <-> Relationship, either dir)  : peer is the Relationship

    The HAS_SOURCE and HAS_OWNER edges from an Attribute, a Node or an OwnerSet stay open.

    For each such edge we close it on the migration branch and create a matching deleted
    edge so that downstream branches see the removal.

    For inbound IS_RELATED, the peer is a Relationship vertex that connects active_node
    and another Node — when active_node is removed, the Relationship is torn down entirely.
    We close its other sub-edges (IS_PROTECTED, HAS_SOURCE, HAS_OWNER, far-side IS_RELATED)
    on the same branch.

    For the other closed edges (HAS_SOURCE and HAS_OWNER from a Relationship, HAS_OWNER_SOURCE),
    the peer belongs to a different Node, so its sub-edges are left alone; only the inbound
    pointer itself is closed.
    """

    name = "migration_node_remove_in"
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params.update(self._build_params())
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        stamp_peer_node, stamp_params = stamp_vertex_metadata(
            "peer_node", at=self.at, operation_ats=self.operation_ats, at_param="current_time"
        )
        self.params.update(stamp_params)
        query = (
            """
    %(selection)s

    // ----------------------------------------------------------
    // For each inbound edge to active_node, find the latest active edge on the branch
    // ----------------------------------------------------------
    MATCH (active_node)<-[r:IS_RELATED|HAS_SOURCE|HAS_OWNER|HAS_OWNER_SOURCE]-(peer:Attribute|Relationship|Node|OwnerSet)
    // The owner and source edges to a removed node stay open, as after the delete of the node.
    WHERE NOT (type(r) IN ["HAS_OWNER", "HAS_SOURCE"] AND NOT peer:Relationship)
    WITH DISTINCT active_node, type(r) AS edge_type, peer
    CALL (active_node, edge_type, peer) {
        MATCH (active_node)<-[r:$(edge_type)]-(peer)
        WHERE %(branch_filter)s
        RETURN r AS rel_inbound, peer AS peer_node
        ORDER BY r.branch_level DESC, r.from DESC
        LIMIT 1
    }
    WITH active_node, rel_inbound, peer_node
    WHERE rel_inbound.status = "active"

    // ----------------------------------------------------------
    // Set updated metadata on the peer vertex on default/global branch
    // ----------------------------------------------------------
    CALL (peer_node) {
        WITH peer_node
        WHERE $set_metadata AND NOT peer_node:OwnerSet
        %(stamp_peer_node)s
    }

    WITH active_node, rel_inbound, peer_node,
            """
            + self._branch_from_existing("rel_inbound")
            + """

    // ----------------------------------------------------------
    // Create a "deleted" edge of the same type and direction
    // ----------------------------------------------------------
    CALL (peer_node, active_node, rel_inbound, new_branch, new_branch_level) {
        CREATE (peer_node)-[new_edge:$(type(rel_inbound))]->(active_node)
        SET new_edge = $rel_props, new_edge.branch = new_branch, new_edge.branch_level = new_branch_level
    }

    // ----------------------------------------------------------
    // Close the existing edge if it lives on the migration branch (or is global)
    // ----------------------------------------------------------
    CALL (rel_inbound) {
        WITH rel_inbound
        WHERE rel_inbound.branch IN [$global_branch, $branch]
        SET rel_inbound.to = $current_time, rel_inbound.to_user_id = $user_id
    }

    // ----------------------------------------------------------
    // For inbound IS_RELATED, the Relationship vertex (peer_node) is being torn down.
    // Close its other sub-edges (IS_PROTECTED, HAS_SOURCE, HAS_OWNER, far-side IS_RELATED)
    // on the same branch. HAS_SOURCE/HAS_OWNER/HAS_OWNER_SOURCE inbound do NOT need this — their peer
    // is or belongs to another Node and stays active.
    // ----------------------------------------------------------
    WITH DISTINCT active_node, peer_node, rel_inbound
    WHERE type(rel_inbound) = "IS_RELATED"

    MATCH (peer_node:Relationship)-[sub_edge]-(sub_peer)
    WHERE sub_peer <> active_node
    WITH DISTINCT peer_node, type(sub_edge) AS sub_edge_type, sub_peer
    CALL (peer_node, sub_edge_type, sub_peer) {
        MATCH (peer_node)-[r:$(sub_edge_type)]-(sub_peer)
        WHERE %(branch_filter)s
        RETURN r AS sub_edge
        ORDER BY r.branch_level DESC, r.from DESC
        LIMIT 1
    }
    WITH peer_node, sub_peer, sub_edge,
            """
            + self._branch_from_existing("sub_edge")
            + """,
            startNode(sub_edge) AS sub_start, endNode(sub_edge) AS sub_end
    WHERE sub_edge.status = "active" AND sub_edge.to IS NULL

    // ----------------------------------------------------------
    // Create a deleted sub-edge of the same type and direction
    // ----------------------------------------------------------
    CALL (sub_start, sub_end, sub_edge, new_branch, new_branch_level) {
        CREATE (sub_start)-[new_edge:$(type(sub_edge))]->(sub_end)
        SET new_edge = $rel_props, new_edge.branch = new_branch, new_edge.branch_level = new_branch_level
    }

    // ----------------------------------------------------------
    // Close the existing sub-edge if it lives on the migration branch or is global
    // ----------------------------------------------------------
    CALL (sub_edge) {
        WITH sub_edge
        WHERE sub_edge.branch IN [$global_branch, $branch]
        SET sub_edge.to = $current_time, sub_edge.to_user_id = $user_id
    }
    """
        ) % {
            "branch_filter": branch_filter,
            "selection": self.render_selection(),
            "stamp_peer_node": stamp_peer_node,
        }
        self.add_to_query(query)

    def get_nbr_migrations_executed(self) -> int:
        return 0


class NodeRemoveMigrationQueryOut(NodeRemoveMigrationBaseQuery):
    """Close outbound edges from nodes of the removed kind, plus their second-level sub-edges.

    Outbound edge types from active_node:
      - HAS_ATTRIBUTE (Node -> Attribute)
      - IS_PART_OF    (Node -> Root)
      - IS_RELATED    (Node <-> Relationship, either dir)
      - HAS_OWNER, HAS_SOURCE, HAS_OWNER_SOURCE (Node -> Node, or HAS_OWNER Node -> NoOwner)
      - HAS_OWNER_SET, HAS_TARGET_OWNER_SET (Node -> OwnerSet)

    After closing the parent HAS_ATTRIBUTE/IS_RELATED/HAS_OWNER_SET/HAS_TARGET_OWNER_SET edge, the
    Attribute/Relationship/OwnerSet vertex is orphaned from active_node's perspective. We must also
    close any active sub-edges hanging off that vertex (HAS_VALUE, HAS_SOURCE, HAS_OWNER,
    HAS_OWNER_SOURCE, IS_PROTECTED, far-side IS_RELATED) on the same branch
    """

    name = "migration_node_remove_out"
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params.update(self._build_params())
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        stamp_active_node, stamp_params = stamp_vertex_metadata(
            "active_node", at=self.at, operation_ats=self.operation_ats, at_param="current_time"
        )
        self.params.update(stamp_params)
        stamp_peer_node, stamp_params = stamp_vertex_metadata(
            "peer_node", at=self.at, operation_ats=self.operation_ats, at_param="current_time"
        )
        self.params.update(stamp_params)
        query = (
            """
    %(selection)s

    // ----------------------------------------------------------
    // Set updated metadata on the Node vertex on default/global branch
    // ----------------------------------------------------------
    CALL (active_node) {
        WITH active_node
        WHERE $set_metadata
        %(stamp_active_node)s
    }

    // ----------------------------------------------------------
    // For each outbound edge from active_node, find the latest active edge on the branch
    // ----------------------------------------------------------
    WITH active_node
    MATCH (active_node)-[
        e:HAS_ATTRIBUTE|IS_RELATED|IS_PART_OF
        |HAS_OWNER|HAS_OWNER_SET|HAS_TARGET_OWNER_SET|HAS_OWNER_SOURCE|HAS_SOURCE
    ]->(peer:Attribute|Relationship|Root|Node|NoOwner|OwnerSet)
    WITH DISTINCT active_node, type(e) AS edge_type, peer
    CALL (active_node, edge_type, peer) {
        MATCH (active_node)-[r:$(edge_type)]->(peer)
        WHERE %(branch_filter)s
        RETURN r AS rel_outbound, peer AS peer_node
        ORDER BY r.branch_level DESC, r.from DESC
        LIMIT 1
    }
    WITH active_node, rel_outbound, peer_node
    WHERE rel_outbound.status = "active"

    // ----------------------------------------------------------
    // Set updated metadata on the peer vertex on default/global branch
    // ----------------------------------------------------------
    CALL (peer_node) {
        WITH peer_node
        WHERE $set_metadata AND (peer_node:Attribute OR peer_node:Relationship)
        %(stamp_peer_node)s
    }

    WITH active_node, rel_outbound, peer_node,
            """
            + self._branch_from_existing("rel_outbound")
            + """

    // ----------------------------------------------------------
    // Create a "deleted" edge of the same type and direction
    // ----------------------------------------------------------
    CALL (active_node, peer_node, rel_outbound, new_branch, new_branch_level) {
        CREATE (active_node)-[new_edge:$(type(rel_outbound))]->(peer_node)
        SET new_edge = $rel_props, new_edge.branch = new_branch, new_edge.branch_level = new_branch_level
    }

    // ----------------------------------------------------------
    // Close the existing parent edge if it lives on the migration branch (or is global)
    // ----------------------------------------------------------
    CALL (rel_outbound) {
        WITH rel_outbound
        WHERE rel_outbound.branch IN [$global_branch, $branch]
        SET rel_outbound.to = $current_time, rel_outbound.to_user_id = $user_id
    }

    // ----------------------------------------------------------
    // Close sub-edges hanging off the Attribute/Relationship/OwnerSet peer vertex
    // ----------------------------------------------------------
    WITH DISTINCT active_node, peer_node
    MATCH (peer_node:Attribute|Relationship|OwnerSet)-[e]-(sub_peer)
    WHERE sub_peer <> active_node
    WITH DISTINCT active_node, peer_node, type(e) AS sub_edge_type, sub_peer
    CALL (peer_node, sub_edge_type, sub_peer) {
        MATCH (peer_node)-[r:$(sub_edge_type)]-(sub_peer)
        WHERE %(branch_filter)s
        RETURN r AS sub_edge
        ORDER BY r.branch_level DESC, r.from DESC
        LIMIT 1
    }
    WITH active_node, peer_node, sub_peer, sub_edge,
            """
            + self._branch_from_existing("sub_edge")
            + """,
            startNode(sub_edge) AS sub_start, endNode(sub_edge) AS sub_end
    WHERE sub_edge.status = "active" AND sub_edge.to IS NULL

    // ----------------------------------------------------------
    // Create a deleted sub-edge of the same type and direction.
    // ----------------------------------------------------------
    CALL (sub_start, sub_end, sub_edge, new_branch, new_branch_level) {
        CREATE (sub_start)-[new_edge:$(type(sub_edge))]->(sub_end)
        SET new_edge = $rel_props, new_edge.branch = new_branch, new_edge.branch_level = new_branch_level
    }

    // ----------------------------------------------------------
    // Close the existing sub-edge if it lives on the migration branch (or is global)
    // ----------------------------------------------------------
    CALL (sub_edge) {
        WITH sub_edge
        WHERE sub_edge.branch IN [$global_branch, $branch]
        SET sub_edge.to = $current_time, sub_edge.to_user_id = $user_id
    }

    RETURN DISTINCT active_node
    """
        ) % {
            "branch_filter": branch_filter,
            "selection": self.render_selection(),
            "stamp_active_node": stamp_active_node,
            "stamp_peer_node": stamp_peer_node,
        }
        self.add_to_query(query)

    def get_nbr_migrations_executed(self) -> int:
        """Only in the outbound query b/c only the outbound query is guaranteed to run."""
        return self.num_of_results


class NodeRemoveMigration(SchemaMigration):
    phase: ClassVar[MigrationPhase] = MigrationPhase.NODE_REMOVE
    name: str = "node.remove"
    queries: Sequence[type[MigrationQuery]] = [NodeRemoveMigrationQueryIn, NodeRemoveMigrationQueryOut]

    @classmethod
    def get_changed_kinds(
        cls, schema_path: SchemaPath, previous_schema: SchemaBranch, new_schema: SchemaBranch
    ) -> frozenset[str]:
        """Add the kinds of the peers, because the removal closes the Relationship vertices it shares with them."""
        changed_kinds = super().get_changed_kinds(
            schema_path=schema_path, previous_schema=previous_schema, new_schema=new_schema
        )
        if not previous_schema.has(name=schema_path.schema_kind):
            return changed_kinds
        removed_schema = previous_schema.get(name=schema_path.schema_kind, duplicate=False)
        return changed_kinds.union(
            *(
                previous_schema.get_dependent_kinds(name=relationship.peer)
                for relationship in removed_schema.relationships
            )
        )
