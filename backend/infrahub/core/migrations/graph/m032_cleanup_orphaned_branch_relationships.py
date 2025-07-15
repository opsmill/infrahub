from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.query.branch import DeleteBranchRelationshipsQuery
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class DeletedBranchCleanupQuery(Query):
    """
    Find all unique edge branch names for which there is no Branch object
    """

    name = "deleted_branch_cleanup"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (b:Branch)
WITH collect(DISTINCT b.name) AS branch_names
MATCH ()-[e]->()
WHERE e.branch IS NOT NULL
AND NOT e.branch IN branch_names
RETURN DISTINCT (e.branch) AS branch_name
        """
        self.add_to_query(query)
        self.return_labels = ["branch_name"]


class DeleteOrphanRelationshipsQuery(Query):
    """
    Find all Relationship vertices that link to fewer than 2 Node vertices and delete them
    """

    name = "delete_orphan_relationships"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (r:Relationship)-[:IS_RELATED]-(n:Node)
WITH DISTINCT r, n
WITH r, count(*) AS node_count
WHERE node_count < 2
DETACH DELETE r
        """
        self.add_to_query(query)


class Migration032(ArbitraryMigration):
    """
    Delete edges for branches that were not completely deleted
    """

    name: str = "032_cleanup_deleted_branches"
    minimum_version: int = 31

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        migration_result = MigrationResult()

        try:
            log.info("Get partially deleted branch names...")
            orphaned_branches_query = await DeletedBranchCleanupQuery.init(db=db)
            await orphaned_branches_query.execute(db=db)

            orphaned_branch_names = []
            for result in orphaned_branches_query.get_results():
                branch_name = result.get_as_type("branch_name", str)
                orphaned_branch_names.append(branch_name)

            if not orphaned_branch_names:
                log.info("No partially deleted branches found. All done.")
                return migration_result

            log.info(f"Found {len(orphaned_branch_names)} orphaned branch names: {orphaned_branch_names}")

            for branch_name in orphaned_branch_names:
                log.info(f"Cleaning up branch '{branch_name}'...")
                delete_query = await DeleteBranchRelationshipsQuery.init(db=db, branch_name=branch_name)
                await delete_query.execute(db=db)
                log.info(f"Branch '{branch_name}' cleaned up.")

            log.info("Deleting orphaned relationships...")
            delete_relationships_query = await DeleteOrphanRelationshipsQuery.init(db=db)
            await delete_relationships_query.execute(db=db)
            log.info("Orphaned relationships deleted.")

        except Exception as exc:
            migration_result.errors.append(str(exc))
            log.exception("Error during branch cleanup")

        return migration_result
