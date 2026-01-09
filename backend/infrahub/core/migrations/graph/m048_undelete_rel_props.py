from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.migrations.graph.m041_deleted_dup_edges import DeleteDuplicatedRelationshipEdges
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class UndeleteRelationshipProperties(Query):
    """
    Find Relationship vertices that are missing IS_VISIBLE and/or IS_PROTECTED edges linking them to Boolean vertices

    Use the existing IS_RELATED edges to determine when the IS_VISIBLE/IS_PROTECTED edges should exist on each branch
    and add the missing edges

    Sets IS_VISIBLE to TRUE and IS_PROTECTED to FALSE
    """

    name = "undelete_relationship_properties"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
// --------------
// find all Relationships that are missing IS_VISIBLE/IS_PROTECTED edges
// --------------
MATCH (rel:Relationship)-[:IS_RELATED]-()
WHERE NOT exists((rel)-[:IS_VISIBLE]->())
OR NOT exists((rel)-[:IS_PROTECTED]->())
WITH DISTINCT rel
WITH rel, exists((rel)-[:IS_VISIBLE]->()) AS has_visible, exists((rel)-[:IS_PROTECTED]->()) AS has_protected
WHERE has_visible = FALSE OR has_protected = FALSE

// --------------
// one row for each branch the Relationship has changes on
// --------------
CALL (rel) {
    MATCH (rel)-[e:IS_RELATED]-()
    RETURN DISTINCT e.branch AS branch
}

// --------------
// get the earliest from edge on this branch, if any
// --------------
CALL (rel, branch) {
    OPTIONAL MATCH (rel)-[e:IS_RELATED {status: "active", branch: branch}]-()
    // ignore schema kind/inheritance migration edges
    WHERE NOT exists((rel)-[:IS_RELATED {status: "deleted", branch: branch, from: e.from}]-())
    RETURN e AS earliest_from_edge
    ORDER BY e.from ASC
    LIMIT 1
}

// --------------
// get the latest to time on this branch, if any
// --------------
CALL (rel, branch) {
    OPTIONAL MATCH (rel)-[e:IS_RELATED {status: "active", branch: branch}]-()
    // ignore schema kind/inheritance migration edges
    WHERE NOT exists((rel)-[:IS_RELATED {status: "active", branch: branch, from: e.to}]-())
    RETURN e.to AS latest_to_time
    ORDER BY e.to DESC
    LIMIT 1
}

// --------------
// get the latest deleted edge on this branch, if any
// --------------
CALL (rel, branch) {
    OPTIONAL MATCH (rel)-[deleted_e:IS_RELATED {status: "deleted", branch: branch}]-()
    // ignore schema kind/inheritance migration edges
    WHERE NOT exists((rel)-[:IS_RELATED {status: "active", branch: branch, from: deleted_e.from}]-())
    RETURN deleted_e AS latest_deleted_edge
    ORDER BY deleted_e.from DESC
    LIMIT 1
}

// --------------
// add active IS_VISIBLE edge on the branch, if necessary
// --------------
CALL (rel, earliest_from_edge, latest_to_time, has_visible) {
    WITH *, has_visible
    WHERE has_visible = FALSE
    AND earliest_from_edge IS NOT NULL
    MERGE (bool:Boolean {value: TRUE})
    CREATE (rel)-[new_edge:IS_VISIBLE]->(bool)
    SET new_edge = properties(earliest_from_edge)
    SET new_edge.to = latest_to_time
}
// --------------
// add deleted IS_VISIBLE edge on the branch, if necessary
// --------------
CALL (rel, latest_deleted_edge, has_visible) {
    WITH *, has_visible
    WHERE has_visible = FALSE
    AND latest_deleted_edge IS NOT NULL
    MERGE (bool:Boolean {value: TRUE})
    CREATE (rel)-[new_edge:IS_VISIBLE]->(bool)
    SET new_edge = properties(latest_deleted_edge)
}
// --------------
// add active IS_PROTECTED edge on the branch, if necessary
// --------------
CALL (rel, earliest_from_edge, latest_to_time, has_protected) {
    WITH *, has_protected
    WHERE has_protected = FALSE
    AND earliest_from_edge IS NOT NULL
    MERGE (bool:Boolean {value: FALSE})
    CREATE (rel)-[new_edge:IS_PROTECTED]->(bool)
    SET new_edge = properties(earliest_from_edge)
    SET new_edge.to = latest_to_time
}
// --------------
// add deleted IS_PROTECTED edge on the branch, if necessary
// --------------
CALL (rel, latest_deleted_edge, has_protected) {
    WITH *, has_protected
    WHERE has_protected = FALSE
    AND latest_deleted_edge IS NOT NULL
    MERGE (bool:Boolean {value: FALSE})
    CREATE (rel)-[new_edge:IS_PROTECTED]->(bool)
    SET new_edge = properties(latest_deleted_edge)
}
        """
        self.add_to_query(query)


class Migration048(ArbitraryMigration):
    """
    Fix Relationship vertices that are missing IS_VISIBLE and/or IS_PROTECTED edges.

    This can happen due to a bug in Migration041 that deleted these edges incorrectly.
    """

    name: str = "048_undelete_rel_props"
    minimum_version: int = 47

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        console = get_migration_console()

        console.log("Deleting duplicate edges for all Relationships", end="...")
        delete_duplicate_edges_query = await DeleteDuplicatedRelationshipEdges.init(
            db=db, migrated_kind_nodes_only=False, at=at
        )
        await delete_duplicate_edges_query.execute(db=db)
        console.log("done")

        console.log("Undeleting Relationship properties", end="...")
        undelete_rel_props_query = await UndeleteRelationshipProperties.init(db=db, at=at)
        await undelete_rel_props_query.execute(db=db)
        console.log("done")

        return MigrationResult()
