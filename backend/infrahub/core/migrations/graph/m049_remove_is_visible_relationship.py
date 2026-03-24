from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration, MigrationInput

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class RemoveIsVisibleRelationshipQuery(Query):
    name = "remove_is_visible_relationship"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH ()-[rel:IS_VISIBLE]->()
        CALL (rel) {
          DELETE rel
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class RemoveIsVisibleFromDiffsQuery(Query):
    name = "remove_is_visible_from_diffs"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (diff_prop:DiffProperty {property_type: "IS_VISIBLE"})
        CALL (diff_prop) {
            DETACH DELETE diff_prop
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class Migration049(GraphMigration):
    name: str = "049_remove_is_visible_relationship"
    minimum_version: int = 48
    queries: Sequence[type[Query]] = [RemoveIsVisibleRelationshipQuery, RemoveIsVisibleFromDiffsQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        return await self.do_execute(migration_input=migration_input)
