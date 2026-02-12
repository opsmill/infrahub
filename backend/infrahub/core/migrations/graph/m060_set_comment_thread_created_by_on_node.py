from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class SetCommentCreatedByOnNodeQuery(Query):
    name = "set_comment_created_by_on_node"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH (comment:CoreComment)
        CALL (comment) {
            MATCH (comment)-[r1:IS_RELATED]-(:Relationship {name: "comment__account"})-[r2:IS_RELATED]-(account:CoreGenericAccount)
            RETURN account
            ORDER BY r1.from DESC, r2.from DESC
            LIMIT 1
        }
        SET comment.created_by = account.uuid
        """
        self.add_to_query(query)


class SetThreadCreatedByOnNodeQuery(Query):
    name = "set_thread_created_by_on_node"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
        MATCH (thread:CoreThread)
        CALL (thread) {
            MATCH (thread)-[r1:IS_RELATED]-(:Relationship {name: "thread__account"})-[r2:IS_RELATED]-(account:CoreGenericAccount)
            RETURN account
            ORDER BY r1.from DESC, r2.from DESC
            LIMIT 1
        }
        SET thread.created_by = account.uuid
        """
        self.add_to_query(query)


class Migration060(GraphMigration):
    name: str = "060_set_comment_thread_created_by_on_node"
    minimum_version: int = 59
    queries: Sequence[type[Query]] = [SetCommentCreatedByOnNodeQuery, SetThreadCreatedByOnNodeQuery]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
