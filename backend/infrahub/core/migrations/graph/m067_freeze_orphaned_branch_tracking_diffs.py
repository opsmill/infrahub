from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration067Query01(Query):
    name = "migration_067_01"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (diff_root:DiffRoot)
        WHERE diff_root.tracking_id STARTS WITH "branch."
        AND (diff_root.is_frozen IS NULL OR diff_root.is_frozen <> TRUE)
        WITH diff_root, substring(diff_root.tracking_id, 7) AS branch_name
        OPTIONAL MATCH (branch:Branch {name: branch_name})
            WHERE branch.status <> "DELETING"
        WITH diff_root, branch, branch_name
        WHERE branch IS NULL
            OR branch.branched_from <> diff_root.from_time
            OR branch.status = "MERGED"
        OPTIONAL MATCH (diff_root)-[:DIFF_HAS_PARTNER]-(partner:DiffRoot)
        SET diff_root.is_frozen = TRUE
        SET diff_root.tracking_id = "frozen." + branch_name
        SET partner.is_frozen = TRUE
        SET partner.tracking_id = "frozen." + branch_name
        """
        self.add_to_query(query)


class Migration067(GraphMigration):
    name: str = "067_freeze_orphaned_branch_tracking_diffs"
    queries: Sequence[type[Query]] = [Migration067Query01]
    minimum_version: int = 66

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
