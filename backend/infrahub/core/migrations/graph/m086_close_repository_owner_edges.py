from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.branch.enums import TERMINAL_BRANCH_STATUSES
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.ownership.report import RepositoryOwnersReportQuery
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class CloseRepositoryOwnerEdgesQuery(Query):
    """Close the open owner edges from attributes to repositories, on every branch, and count them by repository.

    Each edge keeps its `from` time and gets a `to` time, so a read at an earlier time still returns the repository.
    The writes are batched, so this query cannot run inside an explicit transaction. A second run finds no open
    edge.
    """

    name = "migration_086_close_repository_owner_edges"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id
        self.params["batch_size"] = config.SETTINGS.database.query_size_limit
        query = """
MATCH (:Attribute)-[r:HAS_OWNER]->(repository:%(repository_label)s)
WHERE r.status = "active" AND r.to IS NULL
CALL (r) {
    SET r.to = $at, r.to_user_id = $user_id
} IN TRANSACTIONS OF $batch_size ROWS
RETURN repository.uuid AS repository_id, repository.kind AS repository_kind, count(r) AS nb_edges
ORDER BY repository_id
        """ % {"repository_label": InfrahubKind.GENERICREPOSITORY}
        self.add_to_query(query)
        self.return_labels = ["repository_id", "repository_kind", "nb_edges"]

    def get_closed_edges(self) -> list[tuple[str, str, int]]:
        """Return the ID, the kind and the number of closed edges of each repository."""
        return [
            (
                result.get_as_type("repository_id", str),
                result.get_as_type("repository_kind", str),
                result.get_as_type("nb_edges", int),
            )
            for result in self.get_results()
        ]


class HideRepositoryOwnersOnBranchesQuery(Query):
    """Hide, on each branch, the closed owner edges from attributes to repositories that the branch still reads.

    A branch reads the edges of its origin branch at the time of its start, so a `to` time after that start does
    not hide the edge. Each such edge gets a `deleted` edge on the branch at the time of the upgrade, so a read at
    an earlier time still returns the repository. The writes are batched, so this query cannot run inside an
    explicit transaction. A second run finds each `deleted` edge and adds none.
    """

    name = "migration_086_hide_repository_owners_on_branches"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id
        self.params["batch_size"] = config.SETTINGS.database.query_size_limit
        # A merged branch or a branch that is being deleted is not read again.
        self.params["terminal_statuses"] = [status.value for status in TERMINAL_BRANCH_STATUSES]
        query = """
MATCH (b:Branch)
WHERE b.hierarchy_level > 1 AND NOT b.status IN $terminal_statuses
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

    name = "migration_086_hide_global_repository_owners"
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


class Migration086(ArbitraryMigration):
    name: str = "086_close_repository_owner_edges"
    description: str = "Close the owner edges from attributes to repositories, which are no longer owners"
    minimum_version: int = 85

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        try:
            # The close ends these owners, so the operator keeps their list from the log.
            report_query = await RepositoryOwnersReportQuery.init(db=db)
            await report_query.execute(db=db)
            rows = report_query.get_rows()
            migration_input.console.log(
                f"Attributes that a repository owns, before the close: {sum(row.nb_attributes for row in rows)}"
            )
            for row in rows:
                migration_input.console.log(
                    f"  {row.node_kind}.{row.attribute_name}, repository {row.repository_id} ({row.repository_kind}),"
                    f" branch {row.branch}: {row.nb_attributes}"
                )
            close_query = await CloseRepositoryOwnerEdgesQuery.init(
                db=db, at=migration_input.at, user_id=migration_input.user_id
            )
            await close_query.execute(db=db)
            # The close commits in batches, so its counts are printed before a later query can fail.
            closed_edges = close_query.get_closed_edges()
            nb_closed = sum(nb_edges for _, _, nb_edges in closed_edges)
            migration_input.console.log(f"Closed {nb_closed} owner edge(s) from attributes to repositories.")
            for repository_id, repository_kind, nb_edges in closed_edges:
                migration_input.console.log(f"  repository {repository_id} ({repository_kind}): {nb_edges}")
            # The hide queries read the `to` times that the first query sets.
            for query_class in (HideRepositoryOwnersOnBranchesQuery, HideGlobalRepositoryOwnersQuery):
                query = await query_class.init(db=db, at=migration_input.at, user_id=migration_input.user_id)
                await query.execute(db=db)
        # reported through the result so the runner prints it against this migration
        except Exception as exc:  # noqa: BLE001
            return MigrationResult(errors=[str(exc)])
        return MigrationResult(nbr_migrations_executed=nb_closed)
