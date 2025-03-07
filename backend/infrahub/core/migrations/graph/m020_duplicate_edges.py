from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.log import get_logger

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class DeleteDuplicateHasValueEdgesQuery(Query):
    name = "delete_duplicate_has_value_edges"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// -------------------
// find Attribute nodes with multiple identical edges to AttributeValue nodes with the same value
// -------------------
MATCH (a:Attribute)-[e:HAS_VALUE]->(av:AttributeValue)
WITH a, e.branch AS branch, e.branch_level AS branch_level, e.status AS status, e.from AS from, e.to AS to,
    av.value AS attr_val, av.is_default AS attr_default, COUNT(*) AS num_duplicate_edges
WHERE num_duplicate_edges > 1
// -------------------
// get the the one AttributeValue we want to use
// -------------------
WITH DISTINCT a, branch, branch_level, status, from, to, attr_val, attr_default
WITH attr_val, attr_default, collect([a, branch, branch_level, status, from, to]) AS details_list
CALL {
    WITH attr_val, attr_default
    MATCH (av:AttributeValue {value: attr_val, is_default: attr_default})
    RETURN av AS the_one_av
    ORDER by %(id_func)s(av) ASC
    LIMIT 1
}
UNWIND details_list AS details_item
WITH attr_val, attr_default, the_one_av,
    details_item[0] AS a, details_item[1] AS branch, details_item[2] AS branch_level,
    details_item[3] AS status, details_item[4] AS from, details_item[5] AS to
// -------------------
// get/create the one edge to keep
// -------------------
CREATE (a)-[fresh_e:HAS_VALUE {branch: branch, branch_level: branch_level, status: status, from: from}]->(the_one_av)
SET fresh_e.to = to
WITH a, branch, status, from, to, attr_val, attr_default, %(id_func)s(fresh_e) AS e_id_to_keep
// -------------------
// get the identical edges for a given set of Attribute node, edge properties, AttributeValue.value
// -------------------
CALL {
    // -------------------
    // delete the duplicate edges a given set of Attribute node, edge properties, AttributeValue.value
    // -------------------
    WITH a, branch, status, from, to, attr_val, attr_default, e_id_to_keep
    MATCH (a)-[e:HAS_VALUE]->(av:AttributeValue {value: attr_val, is_default: attr_default})
    WHERE %(id_func)s(e) <> e_id_to_keep
    AND e.branch = branch AND e.status = status AND e.from = from
    AND (e.to = to OR (e.to IS NULL AND to IS NULL))
    DELETE e
}
// -------------------
// delete any orphaned AttributeValue nodes
// -------------------
WITH NULL AS nothing
LIMIT 1
MATCH (orphaned_av:AttributeValue)
WHERE NOT exists((orphaned_av)-[]-())
DELETE orphaned_av
        """ % {"id_func": db.get_id_function_name()}
        self.add_to_query(query)


class DeleteDuplicateBooleanEdgesQuery(Query):
    name = "delete_duplicate_booleans_edges"
    type = QueryType.WRITE
    insert_return = False
    edge_type: DatabaseEdgeType | None = None

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        if not self.edge_type:
            raise RuntimeError("edge_type is required for this query")
        query = """
// -------------------
// find Attribute nodes with multiple identical edges to Boolean nodes
// -------------------
MATCH (a:Attribute)-[e:%(edge_type)s]->(b)
WITH a, e.branch AS branch, e.branch_level AS branch_level, e.status AS status, e.from AS from, e.to AS to, b, COUNT(*) AS num_duplicate_edges
WHERE num_duplicate_edges > 1
// -------------------
// get the identical edges for a given set of Attribute node, edge properties, Boolean
// -------------------
WITH DISTINCT a, branch, branch_level, status, from, to, b
CREATE (a)-[fresh_e:%(edge_type)s {branch: branch, branch_level: branch_level, status: status, from: from}]->(b)
SET fresh_e.to = to
WITH a, branch, status, from, to, b, %(id_func)s(fresh_e) AS e_id_to_keep
CALL {
    WITH a, branch, status, from, to, b, e_id_to_keep
    MATCH (a)-[e:%(edge_type)s]->(b)
    WHERE %(id_func)s(e) <> e_id_to_keep
    AND e.branch = branch AND e.status = status AND e.from = from
    AND (e.to = to OR (e.to IS NULL AND to IS NULL))
    DELETE e
}
        """ % {"edge_type": self.edge_type.value, "id_func": db.get_id_function_name()}
        self.add_to_query(query)


class DeleteDuplicateIsVisibleEdgesQuery(DeleteDuplicateBooleanEdgesQuery):
    name = "delete_duplicate_is_visible_edges"
    type = QueryType.WRITE
    insert_return = False
    edge_type = DatabaseEdgeType.IS_VISIBLE


class DeleteDuplicateIsProtectedEdgesQuery(DeleteDuplicateBooleanEdgesQuery):
    name = "delete_duplicate_is_protected_edges"
    type = QueryType.WRITE
    insert_return = False
    edge_type = DatabaseEdgeType.IS_PROTECTED


class Migration020(GraphMigration):
    """
    1. Find duplicate edges. These can be duplicated if multiple AttributeValue nodes with the same value exist b/c of concurrent
        database updates.
        a. (a:Attribute)-[e:HAS_VALUE]->(av:AttributeValue)
            grouped by (a, e.branch, e.from, e.to, e.status, av.value, av.is_default) to determine the number of duplicates.
        b. (a:Attribute)-[e:HAS_VALUE]->(b:Boolean)
            grouped by (a, e.branch, e.from, e.status, b) to determine the number of duplicates.
    2. For a given set of duplicate edges
        a. delete all of the duplicate edges
        b. merge one edge with the properties of the deleted edges
    3. If there are any orphaned AttributeValue nodes after these changes, then delete them

    This migration does not account for consolidating duplicated AttributeValue nodes because more might be created
    in the future due to concurrent database updates. A migration to consolidate duplicated AttributeValue nodes
    should be run when we find a way to stop duplicate AttributeValue nodes from being created
    """

    name: str = "020_delete_duplicate_edges"
    minimum_version: int = 19
    queries: Sequence[type[Query]] = [
        DeleteDuplicateHasValueEdgesQuery,
        DeleteDuplicateIsVisibleEdgesQuery,
        DeleteDuplicateIsProtectedEdgesQuery,
    ]

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        # skip the transaction b/c it will run out of memory on a large database
        return await self.do_execute(db=db)

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
