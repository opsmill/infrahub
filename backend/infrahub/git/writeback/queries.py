from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class RepositoryWriteLockQuery(Query):
    """Take the database write lock of the repository node, which Neo4j holds until the transaction ends.

    Cypher has no lock statement: a write takes the lock, so the query sets a property and removes it again.
    """

    name = "repository-write-lock"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, repository_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["repository_id"] = repository_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (repository:Node {uuid: $repository_id})
        SET repository._write_lock = true
        REMOVE repository._write_lock
        """
        self.add_to_query(query)
