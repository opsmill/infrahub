from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core import registry
from infrahub.core.initialization import initialization
from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.lock import initialize_lock
from infrahub.log import get_logger

from ...query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class BackfillMissingHierarchyQuery(Query):
    name = "backfill_missing_hierarchy"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)
        kind_hierarchy_map: dict[str, str] = {}
        schema_branch = await registry.schema.load_schema_from_db(db=db)
        for node_schema_kind in schema_branch.node_names:
            node_schema = schema_branch.get_node(name=node_schema_kind, duplicate=False)
            if node_schema.hierarchy:
                kind_hierarchy_map[node_schema.kind] = node_schema.hierarchy

        self.params = {"hierarchy_map": kind_hierarchy_map}
        query = """
        MATCH (r:Root)
        WITH r.default_branch AS default_branch
        MATCH (rel:Relationship {name: "parent__child"})-[e:IS_RELATED]-(n:Node)
        WHERE e.hierarchy IS NULL
        WITH DISTINCT rel, n, default_branch
        CALL {
            WITH rel, n, default_branch
            MATCH (rel)-[e:IS_RELATED {branch: default_branch}]-(n)
            RETURN e
            ORDER BY e.from DESC
            LIMIT 1
        }
        WITH rel, n, e
        WHERE e.status = "active" AND e.hierarchy IS NULL
        SET e.hierarchy = $hierarchy_map[n.kind]
        """
        self.add_to_query(query)


class Migration024(GraphMigration):
    """
    A bug in diff merge logic caused the hierarchy information on IS_RELATED edges to be lost when merged into
    main. This migration backfills the missing hierarchy data and accounts for the case when the branch that
    created the data has been deleted.
    """

    name: str = "024_backfill_hierarchy"
    minimum_version: int = 23
    queries: Sequence[type[Query]] = [BackfillMissingHierarchyQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
