from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class SchemaLoadRollbackQuery(Query):
    """Rollback all schema changes made at a specific timestamp on a branch.

    This query reverses database changes made during a schema load operation by:
    1. Resetting `to` times back to NULL for relationships that were closed at the given timestamp
    2. Deleting relationships that were created at the given timestamp

    This is similar to DiffMergeRollbackQuery but operates on a single branch.
    """

    name = "schema_load_rollback"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rollback_at = at
        self.target_branch = target_branch

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "target_branch": self.target_branch.name,
        }
        query = """
        // ---------------------------
        // Reset 'to' times: restore relationships that were closed at this timestamp
        // ---------------------------
        CALL () {
            OPTIONAL MATCH ()-[r_to {to: $at, branch: $target_branch}]-()
            SET r_to.to = NULL
        } IN TRANSACTIONS
        // ---------------------------
        // Delete 'from' times: remove relationships that were created at this timestamp
        // ---------------------------
        CALL () {
            OPTIONAL MATCH ()-[r_from {from: $at, branch: $target_branch}]-()
            DELETE r_from
        } IN TRANSACTIONS
        """
        self.add_to_query(query=query)
