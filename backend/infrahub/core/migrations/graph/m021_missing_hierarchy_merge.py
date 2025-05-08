from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.log import get_logger

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class SetMissingHierarchyQuery(Query):
    name = "set_missing_hierarchy"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH (r:Root)
        WITH r.default_branch AS default_branch
        MATCH (n:Node)-[main_e:IS_RELATED {branch: default_branch}]-(rel:Relationship)
        WHERE main_e.hierarchy IS NULL
        CALL (n, main_e, rel) {
            MATCH (n)-[branch_e:IS_RELATED]-(rel)
            WHERE branch_e.hierarchy IS NOT NULL
            AND branch_e.branch <> main_e.branch
            AND branch_e.from < main_e.from
            SET main_e.hierarchy = branch_e.hierarchy
        }
        """
        self.add_to_query(query)


class Migration021(GraphMigration):
    """
    A bug in diff merge logic caused the hierarchy information on IS_RELATED edges to be lost when merged into
    main. This migration sets the missing hierarchy data.
    """

    name: str = "021_replace_hierarchy"
    minimum_version: int = 20
    queries: Sequence[type[Query]] = [SetMissingHierarchyQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
