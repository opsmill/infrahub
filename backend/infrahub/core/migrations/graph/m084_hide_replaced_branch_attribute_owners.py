from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class HideReplacedBranchAttributeOwnersQuery(Query):
    """Hide the attribute owners that a branch replaced before attributes could have several owners.

    An owner write on a branch left the owner edge of the parent branch active, because a read took only the newest
    owner edge. A read that takes every active owner edge returns both owners. So each replaced owner gets a
    `deleted` edge on the branch, at the time of the first edge of the branch to another owner, so that a read at a
    time between two owner writes of the branch returns one owner. This includes an owner edge that the parent
    branch closed after the start of the branch, because the branch still reads it. It also includes an owner that
    the parent branch added after the start of the branch, which the branch does not read: the merge then closes
    that owner, so the merge keeps the single owner of the branch, as the merge of an earlier release did. A
    repository is left out, because the upgrade closes its owner edges.

    The writes are batched, so this query cannot run inside an explicit transaction. A second run finds no owner to
    hide, because each `deleted` edge is an open edge of the branch to the replaced owner.
    """

    name = "migration_084_hide_replaced_branch_attribute_owners"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["user_id"] = self.user_id
        self.params["batch_size"] = config.SETTINGS.database.query_size_limit
        query = """
MATCH (a:Attribute)-[branch_edge:HAS_OWNER]->(branch_owner:Node)
WHERE branch_edge.branch_level > 1 AND branch_edge.status = "active" AND branch_edge.to IS NULL
MATCH (b:Branch {name: branch_edge.branch})
MATCH (a)-[parent_edge:HAS_OWNER]->(replaced_owner:Node)
WHERE parent_edge.branch_level < branch_edge.branch_level
AND parent_edge.status = "active"
// the branch reads the parent branch at the time of its start, so it still reads an edge that was closed later
AND (parent_edge.to IS NULL OR parent_edge.to > b.branched_from)
AND replaced_owner <> branch_owner
AND NOT replaced_owner:%(repository_label)s
AND NOT EXISTS {
    MATCH (a)-[own_edge:HAS_OWNER]->(replaced_owner)
    WHERE own_edge.branch = branch_edge.branch AND own_edge.to IS NULL
}
MATCH (a)-[written_edge:HAS_OWNER {branch: branch_edge.branch, status: "active"}]->(written_owner:Node)
WHERE written_owner <> replaced_owner
WITH a, replaced_owner, branch_edge.branch AS branch, branch_edge.branch_level AS branch_level,
    min(CASE WHEN parent_edge.from > written_edge.from THEN parent_edge.from ELSE written_edge.from END) AS hidden_at
CALL (a, replaced_owner, branch, branch_level, hidden_at) {
    CREATE (a)-[:HAS_OWNER {
        branch: branch, branch_level: branch_level, status: "deleted", from: hidden_at, from_user_id: $user_id
    }]->(replaced_owner)
} IN TRANSACTIONS OF $batch_size ROWS
        """ % {"repository_label": InfrahubKind.GENERICREPOSITORY}
        self.add_to_query(query)


class Migration084(ArbitraryMigration):
    name: str = "084_hide_replaced_branch_attribute_owners"
    description: str = "Hide the attribute owners that a branch replaced before attributes had several owners"
    minimum_version: int = 83

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        try:
            query = await HideReplacedBranchAttributeOwnersQuery.init(
                db=db, at=migration_input.at, user_id=migration_input.user_id
            )
            await query.execute(db=db)
        # reported through the result so the runner prints it against this migration
        except Exception as exc:  # noqa: BLE001
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()
