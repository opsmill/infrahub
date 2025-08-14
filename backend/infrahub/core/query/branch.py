from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.constants import GLOBAL_BRANCH_NAME
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
// --------------
// for every Node created on this branch (it's about to be deleted), find any agnostic relationships
// connected to the Node and delete them
// --------------
OPTIONAL MATCH (:Root)<-[e:IS_PART_OF {status: "active"}]-(n:Node)
WHERE e.branch = $branch_name
CALL (n) {
    OPTIONAL MATCH (n)-[:IS_RELATED {branch: $global_branch_name}]-(rel:Relationship)
    DETACH DELETE rel
} IN TRANSACTIONS

// reduce the results to a single row
WITH 1 AS one
LIMIT 1

// --------------
// for every edge on this branch, delete it
// --------------
MATCH (s)-[r]->(d)
WHERE r.branch = $branch_name
CALL (r) {
    DELETE r
} IN TRANSACTIONS

// --------------
// get the database IDs of every vertex linked to a deleted edge
// --------------
WITH DISTINCT elementId(s) AS s_id, elementId(d) AS d_id
WITH collect(s_id) + collect(d_id) AS vertex_ids
UNWIND vertex_ids AS vertex_id

// --------------
// delete any vertices that are now orphaned
// --------------
CALL (vertex_id) {
    MATCH (n)
    WHERE elementId(n) = vertex_id
    AND NOT exists((n)--())
    DELETE n
} IN TRANSACTIONS
        """
        self.params["branch_name"] = self.branch_name
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
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
