from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.migrations.shared import GraphMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class FixBranchLevelZeroQuery(Query):
    """Update edges with branch_level=0 to the correct branch_level.

    Edges on the global branch or default branch should have branch_level=1.
    Edges on other branches should have branch_level=2.
    """

    name = "fix_branch_level_zero"
    type: QueryType = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME

        query = """
        MATCH (branch_node:Branch {is_default: true})
        WITH branch_node.name AS default_branch_name
        MATCH ()-[e]->()
        WHERE e.branch_level = 0
        CALL (e, default_branch_name) {
            SET e.branch_level = CASE
                WHEN e.branch = $global_branch_name OR e.branch = default_branch_name THEN 1
                ELSE 2
            END
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class Migration053(GraphMigration):
    """
    Fix edges with branch_level=0 to have the correct branch_level.

    Edges with branch_level=0 indicate a bug where the branch level was not
    properly set during creation. This migration fixes them:
    - Edges on the global branch ("-global-") or default branch: branch_level=1
    - Edges on other branches: branch_level=2
    """

    name: str = "053_fix_branch_level_zero"
    minimum_version: int = 52
    queries: Sequence[type[Query]] = [FixBranchLevelZeroQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        return await self.do_execute(migration_input=migration_input)
