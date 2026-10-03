from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class CountedMigrationQuery(Query):
    type: QueryType = QueryType.WRITE

    insert_return: bool = False
    insert_limit: bool = False

    counter: ClassVar[str] = "relationships_deleted"

    def __init__(self, batch_size: int, **kwargs: Any) -> None:
        self.batch_size = batch_size
        super().__init__(**kwargs)

    def get_count(self) -> int:
        return self.stats.get_counter(self.counter)


class ReanchorNumberPoolRecordsQuery(CountedMigrationQuery):
    """Move every open `IS_RESERVED` edge that still reserves a number onto the owning `Attribute`.

    An edge still reserves a number when some branch can read both the object's attribute and that
    attribute's value being the edge's `AttributeValue`. Each edge is created on the `Attribute` and
    deleted from the `AttributeValue` in the same batch, so a re-run after a failure only finds the edges
    that have not moved yet.
    """

    name: str = "m080_reanchor_number_pool_records"
    counter: ClassVar[str] = "relationships_created"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        self.params["batch_size"] = self.batch_size
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        query = """
// ----------------
// Each branch reads its own edges up to now and its origin branch's edges up to when it branched, so
// an attribute or value removed on the origin branch is still live on a branch created before that
// ----------------
MATCH (branch:Branch)
WHERE branch.status <> "DELETING"
WITH collect({
    name: branch.name,
    origin_name: CASE WHEN branch.is_default OR branch.is_global THEN NULL ELSE branch.origin_branch END,
    origin_at: CASE
        WHEN branch.is_default OR branch.is_global THEN NULL
        WHEN branch.branched_from < $at THEN branch.branched_from
        ELSE $at
    END
}) AS branch_windows
// ----------------
// CoreNumberPool is branch-agnostic, so we can do this simplified check for activeness
// ----------------
MATCH (pool:CoreNumberPool)-[part:IS_PART_OF]->(:Root)
WHERE part.status = "active" AND part.to IS NULL
AND NOT EXISTS {
    MATCH (pool)-[:IS_PART_OF {status: "deleted"}]->(:Root)
}
// ----------------
// Get the attribute name for the pool. The attribute is also branch-agnostic, so this simple check
// is safe. We also prevent changing the "node_attribute" on a NumberPool as of 1.11.x
// ----------------
CALL (pool) {
    MATCH (pool)-[:HAS_ATTRIBUTE]->(:Attribute { name: "node_attribute" })-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL
    RETURN av.value AS attribute_name
    ORDER BY hv.from DESC
    LIMIT 1
}
// ----------------
// The pre-upgrade code never closed an IS_RESERVED edge except to replace it, so only open ones matter
// ----------------
MATCH (pool)-[res:IS_RESERVED]->(reserved:AttributeValue)
WHERE res.status = "active" AND res.to IS NULL
// ----------------
// The pre-upgrade code released a number only by deleting or updating the attribute, so the edge is
// kept for an attribute that some branch still reads as owned by the object and holding the reserved value
// ----------------
MATCH (node:Node { uuid: res.identifier })-[:HAS_ATTRIBUTE]->(attr:Attribute { name: attribute_name })-[:HAS_VALUE]->(reserved)
WITH DISTINCT pool, res, reserved.value AS reserved_value, node, attr, branch_windows
UNWIND branch_windows AS branch_window
// ----------------
// The latest HAS_ATTRIBUTE edge this branch can see
// ----------------
CALL (node, attr, branch_window) {
    MATCH (node)-[has_attribute:HAS_ATTRIBUTE]->(attr)
    WHERE (has_attribute.branch IN [$global_branch_name, branch_window.name]
           AND has_attribute.from <= $at
           AND (has_attribute.to IS NULL OR has_attribute.to > $at))
       OR (has_attribute.branch = branch_window.origin_name
           AND has_attribute.from <= branch_window.origin_at
           AND (has_attribute.to IS NULL OR has_attribute.to > branch_window.origin_at))
    RETURN has_attribute.status = "active" AS attribute_is_active
    ORDER BY has_attribute.branch_level DESC, has_attribute.from DESC, has_attribute.status ASC
    LIMIT 1
}
WITH pool, res, reserved_value, node, attr, branch_window
WHERE attribute_is_active = TRUE
// ----------------
// The latest HAS_VALUE edge this branch can see
// ----------------
CALL (attr, branch_window) {
    MATCH (attr)-[has_value:HAS_VALUE]->(value)
    WHERE (has_value.branch IN [$global_branch_name, branch_window.name]
           AND has_value.from <= $at
           AND (has_value.to IS NULL OR has_value.to > $at))
       OR (has_value.branch = branch_window.origin_name
           AND has_value.from <= branch_window.origin_at
           AND (has_value.to IS NULL OR has_value.to > branch_window.origin_at))
    RETURN has_value.status = "active" AS value_is_active, value.value AS latest_value
    ORDER BY has_value.branch_level DESC, has_value.from DESC, has_value.status ASC
    LIMIT 1
}
// ----------------
// Only make the new edge if everything is active and this value matches the reserved value
// ----------------
WITH pool, res, attr
WHERE value_is_active AND latest_value = reserved_value
WITH pool, res, collect(DISTINCT attr) AS attrs
// ----------------
// Create the new IS_RESERVED edge and delete the old one
// ----------------
CALL (pool, res, attrs) {
    UNWIND attrs AS attr
    CREATE (pool)-[new_res:IS_RESERVED]->(attr)
    SET new_res = properties(res)
    WITH DISTINCT res
    DELETE res
} IN TRANSACTIONS OF $batch_size ROWS
"""
        self.add_to_query(query)


class DeletePoolSourceEdgesQuery(CountedMigrationQuery):
    """Delete every `HAS_SOURCE` edge from an `Attribute` to a number pool."""

    name: str = "m080_delete_pool_source_edges"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["batch_size"] = self.batch_size
        query = """
MATCH (:Attribute)-[hs:HAS_SOURCE]->(:CoreNumberPool)
CALL (hs) {
    DELETE hs
} IN TRANSACTIONS OF $batch_size ROWS
"""
        self.add_to_query(query)


class CollapseSharedAttributeRecordsQuery(CountedMigrationQuery):
    """Leave one live `IS_RESERVED` edge per `Attribute`, whatever pool holds it.

    The newest edge's pool survives because the most recent claim on a number is the current one, and
    it takes the earliest `from` because the attribute has been reserved since then.
    """

    name: str = "m080_collapse_shared_attribute_records"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["batch_size"] = self.batch_size
        query = """
MATCH (:CoreNumberPool)-[res:IS_RESERVED]->(attr:Attribute)
WHERE res.status = "active" AND res.to IS NULL
WITH attr, res
ORDER BY res.from DESC, elementId(res) ASC
WITH attr, collect(res) AS records
WHERE size(records) > 1
WITH
    head(records) AS survivor,
    tail(records) AS losers,
    reduce(earliest = head(records).from, record IN records |
        CASE WHEN record.from < earliest THEN record.from ELSE earliest END) AS earliest
CALL (survivor, losers, earliest) {
    SET survivor.from = earliest
    WITH losers
    UNWIND losers AS loser
    DELETE loser
} IN TRANSACTIONS OF $batch_size ROWS
"""
        self.add_to_query(query)


class DeleteLegacyRecordsQuery(CountedMigrationQuery):
    """Delete every `IS_RESERVED` edge from a number pool still on an `AttributeValue` vertex.

    Anything left there once the re-anchoring has run no longer reserves a number on any branch.
    """

    name: str = "m080_delete_legacy_records"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["batch_size"] = self.batch_size
        query = """
MATCH (:CoreNumberPool)-[res:IS_RESERVED]->(:AttributeValue)
CALL (res) {
    DELETE res
} IN TRANSACTIONS OF $batch_size ROWS
"""
        self.add_to_query(query)


class LeftoverCountsQuery(Query):
    """Count what each pass of the migration should have left at zero."""

    name: str = "m080_leftover_counts"
    type: QueryType = QueryType.READ

    insert_return: bool = False
    insert_limit: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
CALL () {
    MATCH (:CoreNumberPool)-[res:IS_RESERVED]->(attr:Attribute)
    WHERE res.status = "active" AND res.to IS NULL
    WITH attr, count(res) AS records
    WHERE records > 1
    RETURN sum(records - 1) AS shared_attribute_records
}
RETURN
    COUNT { MATCH (:CoreNumberPool)-[:IS_RESERVED]->(:AttributeValue) } AS legacy_records,
    COUNT { MATCH (:Attribute)-[:HAS_SOURCE]->(:CoreNumberPool) } AS pool_source_edges,
    shared_attribute_records
"""
        self.add_to_query(query)
        self.update_return_labels(["legacy_records", "pool_source_edges", "shared_attribute_records"])

    def _count(self, label: str) -> int:
        result = self.get_result()
        if result is None:
            return 0
        return result.get_as_type(label, int)

    def legacy_record_count(self) -> int:
        return self._count("legacy_records")

    def pool_source_edge_count(self) -> int:
        return self._count("pool_source_edges")

    def shared_attribute_record_count(self) -> int:
        return self._count("shared_attribute_records")
