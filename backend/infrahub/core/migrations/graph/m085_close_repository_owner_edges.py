from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class CloseRepositoryOwnerEdgesQuery(Query):
    """Close the open owner edges from attributes to repositories, on every branch.

    Each edge keeps its `from` time and gets a `to` time, so a read at an earlier time still returns the repository.
    The writes are batched, so this query cannot run inside an explicit transaction. A second run finds no open
    edge.
    """

    name = "migration_085_close_repository_owner_edges"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id
        self.params["batch_size"] = config.SETTINGS.database.query_size_limit
        query = """
MATCH (:Attribute)-[r:HAS_OWNER]->(:%(repository_label)s)
WHERE r.status = "active" AND r.to IS NULL
CALL (r) {
    SET r.to = $at, r.to_user_id = $user_id
} IN TRANSACTIONS OF $batch_size ROWS
        """ % {"repository_label": InfrahubKind.GENERICREPOSITORY}
        self.add_to_query(query)


class HideRepositoryOwnersOnBranchesQuery(Query):
    """Hide, on each branch, the closed owner edges from attributes to repositories that the branch still reads.

    A branch reads the edges of its origin branch at the time of its start, so a `to` time after that start does
    not hide the edge. Each such edge gets a `deleted` edge on the branch at the time of the upgrade, so a read at
    an earlier time still returns the repository. The writes are batched, so this query cannot run inside an
    explicit transaction. A second run finds each `deleted` edge and adds none.
    """

    name = "migration_085_hide_repository_owners_on_branches"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id
        self.params["batch_size"] = config.SETTINGS.database.query_size_limit
        query = """
MATCH (b:Branch)
WHERE b.hierarchy_level > 1
MATCH (a:Attribute)-[r:HAS_OWNER]->(repository:%(repository_label)s)
WHERE r.branch = b.origin_branch AND r.status = "active"
AND r.from <= b.branched_from AND r.to > b.branched_from
AND NOT EXISTS {
    MATCH (a)-[hidden:HAS_OWNER {branch: b.name, status: "deleted"}]->(repository)
    WHERE hidden.to IS NULL
}
WITH DISTINCT a, repository, b
CALL (a, repository, b) {
    CREATE (a)-[:HAS_OWNER {
        branch: b.name, branch_level: b.hierarchy_level, status: "deleted", from: $at, from_user_id: $user_id
    }]->(repository)
} IN TRANSACTIONS OF $batch_size ROWS
        """ % {"repository_label": InfrahubKind.GENERICREPOSITORY}
        self.add_to_query(query)


class HideGlobalRepositoryOwnersQuery(Query):
    """Hide the closed global owner edges from attributes to repositories that a branch still reads.

    A branch reads the global edges at the time of its start also, so a `to` time after that start does not hide
    the edge. Each such edge gets a `deleted` edge on the global branch at the time of the upgrade, as a write of
    owners on the global branch does. A read at an earlier time still returns the repository. The writes are
    batched, so this query cannot run inside an explicit transaction. A second run finds each `deleted` edge and
    adds none.
    """

    name = "migration_085_hide_global_repository_owners"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id
        self.params["batch_size"] = config.SETTINGS.database.query_size_limit
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        query = """
MATCH (a:Attribute)-[r:HAS_OWNER {branch: $global_branch_name, status: "active"}]->(repository:%(repository_label)s)
WHERE r.to IS NOT NULL
AND EXISTS {
    MATCH (b:Branch)
    WHERE b.hierarchy_level > 1 AND r.from <= b.branched_from AND r.to > b.branched_from
}
AND NOT EXISTS {
    MATCH (a)-[hidden:HAS_OWNER {branch: $global_branch_name, status: "deleted"}]->(repository)
    WHERE hidden.from >= r.to
}
WITH DISTINCT a, repository
CALL (a, repository) {
    CREATE (a)-[:HAS_OWNER {
        branch: $global_branch_name, branch_level: 1, status: "deleted", from: $at, from_user_id: $user_id
    }]->(repository)
} IN TRANSACTIONS OF $batch_size ROWS
        """ % {"repository_label": InfrahubKind.GENERICREPOSITORY}
        self.add_to_query(query)


class Migration085(ArbitraryMigration):
    name: str = "085_close_repository_owner_edges"
    description: str = "Close the owner edges from attributes to repositories, which are no longer owners"
    minimum_version: int = 84

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        try:
            # The hide queries read the `to` times that the first query sets.
            for query_class in (
                CloseRepositoryOwnerEdgesQuery,
                HideRepositoryOwnersOnBranchesQuery,
                HideGlobalRepositoryOwnersQuery,
            ):
                query = await query_class.init(
                    db=migration_input.db, at=migration_input.at, user_id=migration_input.user_id
                )
                await query.execute(db=migration_input.db)
        # reported through the result so the runner prints it against this migration
        except Exception as exc:  # noqa: BLE001
            return MigrationResult(errors=[str(exc)])
        return MigrationResult()
