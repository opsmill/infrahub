from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationResult
from infrahub.core.timestamp import Timestamp
from infrahub.lock import initialize_lock
from infrahub.log import get_logger

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class FindOrphanedSchemaFieldsQuery(Query):
    name = "find_orphaned_schema_fields"
    type = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// ------------
// Find orphaned SchemaRelationship and SchemaAttribute vertices
// ------------
MATCH (schema_field:SchemaRelationship|SchemaAttribute)-[e:IS_RELATED]-(rel:Relationship)
WHERE rel.name IN ["schema__node__relationships", "schema__node__attributes"]
AND e.status = "deleted" OR e.to IS NOT NULL
WITH schema_field, e.branch AS branch, CASE
    WHEN e.status = "deleted" THEN e.from
    ELSE e.to
END AS delete_time
CALL (schema_field, branch) {
    OPTIONAL MATCH (schema_field)-[is_part_of:IS_PART_OF {branch: branch}]->(:Root)
    WHERE is_part_of.status = "deleted" OR is_part_of.to IS NOT NULL
    RETURN is_part_of IS NOT NULL AS is_deleted
}
WITH schema_field, branch, delete_time
WHERE is_deleted = FALSE
        """
        self.add_to_query(query)
        self.return_labels = ["schema_field.uuid AS schema_field_uuid", "branch", "delete_time"]


class Migration034(ArbitraryMigration):
    """
    Finds active SchemaRelationship and SchemaAttribute vertices with deleted relationships to SchemaNodes or
    SchemaGenerics and deletes them on the same branch at the same time
    """

    name: str = "034_find_orphaned_schema_fields"
    minimum_version: int = 33
    queries: Sequence[type[Query]] = [FindOrphanedSchemaFieldsQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        try:
            initialize_lock()
            await initialization(db=db)
            query = await FindOrphanedSchemaFieldsQuery.init(db=db)
            await query.execute(db=db)
            schema_field_uuids_by_branch: dict[str, dict[str, str]] = defaultdict(dict)
            for result in query.get_results():
                schema_field_uuid = result.get_as_type("schema_field_uuid", return_type=str)
                branch = result.get_as_type("branch", return_type=str)
                delete_time = result.get_as_type("delete_time", return_type=str)
                schema_field_uuids_by_branch[branch][schema_field_uuid] = delete_time

            for branch, schema_rel_details in schema_field_uuids_by_branch.items():
                node_map = await NodeManager.get_many(db=db, branch=branch, ids=list(schema_rel_details.keys()))
                for schema_field_uuid, orphan_schema_rel_node in node_map.items():
                    delete_time = Timestamp(schema_rel_details[schema_field_uuid])
                    await orphan_schema_rel_node.delete(db=db, at=delete_time)
        except Exception as exc:
            log.exception("Error during orphaned schema field cleanup")
            return MigrationResult(errors=[str(exc)])

        return MigrationResult()
