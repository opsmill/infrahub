from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import RelationshipStatus
from infrahub.core.query import QueryType
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import retry_db_transaction

from ..query import MigrationBaseQuery
from ..shared import MigrationResult, RelationshipSchemaMigration

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..shared import MigrationInput


@dataclass(frozen=True)
class RelationshipRemoveQueryParams:
    """Everything the Cypher query needs, computed by the migration from the schema."""

    node_kinds: list[str]
    kinds_to_skip: list[str]
    rel_identifiers: list[str]


class RelationshipMigrationQuery(MigrationBaseQuery):
    type: QueryType = QueryType.WRITE

    def __init__(self, migration: RelationshipSchemaMigration, **kwargs: Any) -> None:
        self.migration = migration
        super().__init__(**kwargs)


class NodeRelationshipRemoveMigrationQuery(RelationshipMigrationQuery):
    """Close the graph data for a relationship, given a precomputed set of parameters.

    For every node of the given kinds, every ``Relationship`` vertex carrying one of the given
    identifiers is torn down: both ``IS_RELATED`` edges and the vertex's ``IS_PROTECTED`` /
    ``HAS_SOURCE`` / ``HAS_OWNER`` sub-edges. A vertex is skipped when either of its endpoint nodes is
    one of ``kinds_to_skip`` (a kind that still declares the identifier, e.g. a surviving inverse side
    or an inheriting kind that overrides the relationship). Because the data is only closed once no
    schema references the identifier, edge direction does not need to be considered.

    An active edge created on the branch the migration runs on is closed in place (its ``to`` time is
    set); an active edge inherited from a parent/global branch is left intact and shadowed by a new
    ``deleted`` edge on the migration branch.
    """

    name = "migration_node_relationship_remove"
    insert_return: bool = False

    def __init__(self, query_params: RelationshipRemoveQueryParams, **kwargs: Any) -> None:
        self.query_params = query_params
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        params = self.query_params

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["kinds_to_skip"] = params.kinds_to_skip
        self.params["rel_identifiers"] = params.rel_identifiers
        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name
        self.params["user_id"] = self.user_id
        self.params["set_metadata"] = self.branch.is_default or self.branch.is_global
        self.params["rel_prop"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }

        query_template = """
        // ----------------------------------------------------------
        // Find all active nodes of the kind the relationship was removed from
        // ----------------------------------------------------------
        MATCH (node:%(node_kinds)s)
        WHERE none(label IN labels(node) WHERE label IN $kinds_to_skip)
        CALL (node) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN r AS root_edge
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH node AS active_node, root_edge
        WHERE root_edge.status = "active"

        // ----------------------------------------------------------
        // Find the Relationship vertices of the removed identifier connected to the node
        // ----------------------------------------------------------
        MATCH (active_node)-[:IS_RELATED]-(rel:Relationship)
        WHERE rel.name IN $rel_identifiers
        WITH DISTINCT active_node, rel

        // The relationship must be currently active for this node on the branch
        CALL (active_node, rel) {
            MATCH (active_node)-[r:IS_RELATED]-(rel)
            WHERE %(branch_filter)s
            RETURN r AS near_edge
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH active_node, rel, near_edge
        WHERE near_edge.status = "active"

        // Resolve the peer on the far side (a distinct node) from its active edge, and skip the vertex
        // when the peer's kind still declares the identifier
        CALL (active_node, rel) {
            MATCH (rel)-[r:IS_RELATED]-(far_peer)
            WHERE far_peer <> active_node AND %(branch_filter)s
            RETURN far_peer, r AS far_edge
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH active_node, rel, far_peer, far_edge
        WHERE far_edge.status = "active"
          AND none(label IN labels(far_peer) WHERE label IN $kinds_to_skip)

        // ----------------------------------------------------------
        // Update metadata on the Relationship vertex and node on default/global branch
        // ----------------------------------------------------------
        CALL (active_node, rel) {
            WITH active_node, rel
            WHERE $set_metadata
            SET rel.previous_updated_at = CASE
                    WHEN rel.updated_at IS NULL OR rel.updated_at <> $current_time THEN rel.updated_at
                    ELSE rel.previous_updated_at
                END,
                rel.previous_updated_by = CASE
                    WHEN rel.updated_at IS NULL OR rel.updated_at <> $current_time THEN rel.updated_by
                    ELSE rel.previous_updated_by
                END
            SET rel.updated_at = $current_time, rel.updated_by = $user_id
            SET active_node.previous_updated_at = CASE
                    WHEN active_node.updated_at IS NULL OR active_node.updated_at <> $current_time THEN active_node.updated_at
                    ELSE active_node.previous_updated_at
                END,
                active_node.previous_updated_by = CASE
                    WHEN active_node.updated_at IS NULL OR active_node.updated_at <> $current_time THEN active_node.updated_by
                    ELSE active_node.previous_updated_by
                END
            SET active_node.updated_at = $current_time, active_node.updated_by = $user_id
        }

        // ----------------------------------------------------------
        // Close every edge of the Relationship vertex (both IS_RELATED edges and the sub-edges)
        // ----------------------------------------------------------
        WITH DISTINCT rel
        MATCH (rel)-[edge]-(peer)
        WITH DISTINCT rel, type(edge) AS edge_type, peer
        CALL (rel, edge_type, peer) {
            MATCH (rel)-[r:$(edge_type)]-(peer)
            WHERE %(branch_filter)s
            RETURN r AS active_edge
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH rel, peer, active_edge, startNode(active_edge) AS edge_start, endNode(active_edge) AS edge_end
        WHERE active_edge.status = "active"

        // Inherited edge (parent/global branch): shadow it with a deleted edge on the migration branch
        CALL (edge_start, edge_end, active_edge) {
            WITH edge_start, edge_end, active_edge
            WHERE active_edge.branch <> $branch_name
            CREATE (edge_start)-[new_edge:$(type(active_edge))]->(edge_end)
            SET new_edge = $rel_prop, new_edge.hierarchy = active_edge.hierarchy
        }
        // Edge created on this branch: close it in place
        CALL (active_edge) {
            WITH active_edge
            WHERE active_edge.branch = $branch_name AND active_edge.to IS NULL
            SET active_edge.to = $current_time, active_edge.to_user_id = $user_id
        }
        // Update metadata on the peer node on default/global branch
        CALL (peer) {
            WITH peer
            WHERE $set_metadata AND peer:Node
            SET peer.previous_updated_at = CASE
                    WHEN peer.updated_at IS NULL OR peer.updated_at <> $current_time THEN peer.updated_at
                    ELSE peer.previous_updated_at
                END,
                peer.previous_updated_by = CASE
                    WHEN peer.updated_at IS NULL OR peer.updated_at <> $current_time THEN peer.updated_by
                    ELSE peer.previous_updated_by
                END
            SET peer.updated_at = $current_time, peer.updated_by = $user_id
        }

        RETURN DISTINCT rel
        """
        query = query_template % {
            "branch_filter": branch_filter,
            "node_kinds": "|".join(params.node_kinds),
        }
        self.add_to_query(query)


class NodeRelationshipRemoveMigration(RelationshipSchemaMigration):
    name: str = "node.relationship.remove"
    queries: Sequence[type[RelationshipMigrationQuery]] = [NodeRelationshipRemoveMigrationQuery]  # type: ignore[assignment]

    def _build_query_params(self, db: InfrahubDatabase, branch: Branch) -> RelationshipRemoveQueryParams | None:
        """Analyse the schema and return the query parameters, or None if there is nothing to close.

        The data of a relationship is shared by both of its schema sides (an outbound relationship and
        its inbound inverse share the same identifier and the same ``Relationship`` vertices). It is
        only closed once no schema still uses the identifier for the affected peers. When the node's own
        kind or the peer kind still declares the identifier, every vertex would be skipped, so the
        migration short-circuits and runs no query.
        """
        previous_relationship = self.previous_relationship_schema
        node_kind = self.previous_schema.kind
        identifier = previous_relationship.get_identifier()

        # Kinds that still declare the identifier in the (post-update) schema keep the relationship data
        # alive (a surviving inverse side, or an inheriting kind that overrides and keeps it), so their
        # vertices must be skipped.
        kinds_to_skip: set[str] = set()
        for other_schema in db.schema.get_full(branch=branch).values():
            if not isinstance(other_schema, (NodeSchema, GenericSchema)):
                continue
            if not any(rel.identifier == identifier for rel in other_schema.relationships):
                continue
            still_declaring = [other_schema.kind]
            if isinstance(other_schema, GenericSchema):
                still_declaring.extend(other_schema.used_by)
            for kind in still_declaring:
                kinds_to_skip.update([kind, f"Profile{kind}", f"Template{kind}"])

        # If the node itself or its peer still declares the identifier, no vertex would be closed.
        if node_kind in kinds_to_skip or previous_relationship.peer in kinds_to_skip:
            return None

        # Expand the population to the profile and object-template copies of the kind, and for a generic
        # to the profile/template copies of the kinds that inherit it.
        node_kinds: list[str] = [node_kind, f"Profile{node_kind}", f"Template{node_kind}"]
        schema = db.schema.get(name=node_kind, branch=branch, duplicate=False)
        if isinstance(schema, GenericSchema):
            for inheriting_kind in schema.used_by:
                node_kinds.extend([f"Profile{inheriting_kind}", f"Template{inheriting_kind}"])

        # Profiles and object templates replicate the relationship under "profile_"/"template_"-prefixed
        # identifiers, and the schema diff never emits a migration for those kinds, so all three close.
        rel_identifiers = [identifier, f"profile_{identifier}", f"template_{identifier}"]

        return RelationshipRemoveQueryParams(
            node_kinds=node_kinds,
            kinds_to_skip=sorted(kinds_to_skip),
            rel_identifiers=rel_identifiers,
        )

    @retry_db_transaction(name="relationship_remove_schema_migration")
    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,  # noqa: ARG002
    ) -> MigrationResult:
        result = MigrationResult()

        query_params = self._build_query_params(db=migration_input.db, branch=branch)
        if query_params is None:
            return result

        async with migration_input.db.start_transaction() as ts:
            query = await NodeRelationshipRemoveMigrationQuery.init(
                db=ts,
                branch=branch,
                at=migration_input.at,
                migration=self,
                user_id=migration_input.user_id,
                query_params=query_params,
            )
            await query.execute(db=ts)
            result.nbr_migrations_executed += query.get_nbr_migrations_executed()

        return result
