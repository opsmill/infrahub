from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.migrations.shared import GraphMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class FixGlobalBranchLevelQuery(Query):
    """Update edges on the global branch to have branch_level = 1."""

    name = "fix_global_branch_level"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME

        query = """
        MATCH ()-[e {branch: $global_branch_name}]->()
        WHERE e.branch_level <> 1
        CALL (e) {
            SET e.branch_level = 1
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class Migration052(GraphMigration):
    """
    Fix edges on the global branch that have incorrect branch_level.

    Edges on the global branch ("-global-") should always have branch_level = 1.
    This migration corrects any edges that were incorrectly created with a different
    branch_level value (e.g., branch_level = 2 when created from a user branch).
    """

    name: str = "052_fix_global_branch_level"
    minimum_version: int = 51
    queries: Sequence[type[Query]] = [FixGlobalBranchLevelQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        return await self.do_execute(migration_input=migration_input)
