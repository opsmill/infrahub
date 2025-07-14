from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class DeleteBranchRelationshipsQuery(Query):
    name: str = "delete_branch_relationships"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, branch_name: str, **kwargs: Any):
        self.branch_name = branch_name
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
// delete all relationships on this branch
MATCH (s)-[r1]-(d)
WHERE r1.branch = $branch_name
CALL (r1) {
  DELETE r1
} IN TRANSACTIONS

// check for any orphaned Node vertices and delete them
WITH collect(DISTINCT s.uuid) + collect(DISTINCT d.uuid) AS nodes_uuids
MATCH (s2:Node)-[r2]-(d2)
WHERE NOT exists((s2)-[:IS_PART_OF]-(:Root))
AND s2.uuid IN nodes_uuids
CALL (r2) {
  DELETE r2
} IN TRANSACTIONS

// reduce results to a single row
WITH 1 AS one LIMIT 1

// find any orphaned vertices and delete them
MATCH (n)
WHERE NOT exists((n)--())
CALL (n) {
  DELETE n
} IN TRANSACTIONS
        """
        self.params["branch_name"] = self.branch_name
        self.add_to_query(query)


class GetAllBranchInternalRelationshipQuery(Query):
    name: str = "get_internal_relationship"

    type: QueryType = QueryType.READ
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH p = ()-[r]-()
        WHERE r.branch = $branch_name
        RETURN DISTINCT r
        """
        self.add_to_query(query=query)
        self.params["branch_name"] = self.branch.name
        self.return_labels = ["r"]


class RebaseBranchUpdateRelationshipQuery(Query):
    name: str = "rebase_branch_update"

    type: QueryType = QueryType.WRITE

    def __init__(self, ids: list[str], **kwargs: Any) -> None:
        self.ids = ids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH ()-[r]->()
        WHERE %(id_func)s(r) IN $ids
        SET r.from = $at
        SET r.conflict = NULL
        """ % {
            "id_func": db.get_id_function_name(),
        }

        self.add_to_query(query=query)

        self.params["at"] = self.at.to_string()
        self.params["ids"] = [db.to_database_id(id) for id in self.ids]
        self.return_labels = [f"{db.get_id_function_name()}(r)"]


class RebaseBranchDeleteRelationshipQuery(Query):
    name: str = "rebase_branch_delete"

    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    def __init__(self, ids: list[str], **kwargs: Any) -> None:
        self.ids = ids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        if config.SETTINGS.database.db_type == config.DatabaseType.MEMGRAPH:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE %(id_func)s(r) IN $ids
            DELETE r
            """
        else:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE %(id_func)s(r) IN $ids
            DELETE r
            WITH *
            UNWIND nodes(p) AS n
            MATCH (n)
            WHERE NOT exists((n)--())
            DELETE n
            """
        query %= {
            "id_func": db.get_id_function_name(),
        }

        self.add_to_query(query=query)

        self.params["ids"] = [db.to_database_id(id) for id in self.ids]
