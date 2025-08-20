from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.root import Root

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration001Query01(Query):
    name = "migration_001_01"
    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH (root:Root)
        SET root.graph_version = 1
        """
        self.add_to_query(query)
        self.return_labels = ["root"]


class Migration001(GraphMigration):
    name: str = "001_add_version_to_graph"
    queries: Sequence[type[Query]] = [Migration001Query01]
    minimum_version: int = 0

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        roots = await Root.get_list(db=db)
        if len(roots) == 0:
            result.errors.append("Unable to find the root node")
        elif len(roots) > 1:
            result.errors.append("Database is corrupted, more than 1 root node found.")

        if result.errors:
            return result

        root_node = roots[0]
        if root_node.graph_version != 1:
            result.errors.append(f"The version of the graph should be 1, found {root_node.graph_version!r} instead.")

        return result
