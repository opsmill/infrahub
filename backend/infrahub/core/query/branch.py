from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

from infrahub import config
from infrahub.core.constants import RelationshipStatus
from infrahub.core.query import Query, QueryType
from infrahub.core.utils import element_id_to_id

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AddNodeToBranch(Query):
    name: str = "node_add_to_branch"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, node_id: int, *args: Any, **kwargs: Any):
        self.node_id = node_id
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        query = """
        MATCH (root:Root)
        MATCH (d) WHERE ID(d) = $node_id
        WITH root,d
        CREATE (d)-[r:IS_PART_OF { branch: $branch, branch_level: $branch_level, from: $now, to: null, status: $status }]->(root)
        RETURN ID(r)
        """

        self.params["node_id"] = element_id_to_id(self.node_id)
        self.params["now"] = self.at.to_string()
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["status"] = RelationshipStatus.ACTIVE.value

        self.add_to_query(query)


class DeleteBranchRelationshipsQuery(Query):
    name: str = "delete_branch_relationships"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, branch_name: str, *args: Any, **kwargs: Any):
        self.branch_name = branch_name
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        if config.SETTINGS.database.db_type == config.DatabaseType.MEMGRAPH:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE r.branch = $branch_name
            DELETE r
            """
        else:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE r.branch = $branch_name
            DELETE r
            WITH *
            UNWIND nodes(p) AS n
            MATCH (n)
            WHERE NOT exists((n)--())
            DELETE n
            """
        self.params["branch_name"] = self.branch_name
        self.add_to_query(query)


class GetAllBranchInternalRelationshipQuery(Query):
    name: str = "get_internal_relationship"

    type: QueryType = QueryType.READ
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
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

    def __init__(self, ids: List[str], *args: Any, **kwargs: Any) -> None:
        self.ids = ids
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        query = """
        MATCH ()-[r]->()
        WHERE ID(r) IN $ids
        SET r.from = $at
        SET r.conflict = NULL
        """

        self.add_to_query(query=query)

        self.params["at"] = self.at.to_string()
        self.params["ids"] = [element_id_to_id(id) for id in self.ids]
        self.return_labels = ["ID(r)"]


class RebaseBranchDeleteRelationshipQuery(Query):
    name: str = "rebase_branch_delete"

    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    def __init__(self, ids: List[str], *args: Any, **kwargs: Any) -> None:
        self.ids = ids
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        if config.SETTINGS.database.db_type == config.DatabaseType.MEMGRAPH:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE ID(r) IN $ids
            DELETE r
            """
        else:
            query = """
            MATCH p = (s)-[r]-(d)
            WHERE ID(r) IN $ids
            DELETE r
            WITH *
            UNWIND nodes(p) AS n
            MATCH (n)
            WHERE NOT exists((n)--())
            DELETE n
            """

        self.add_to_query(query=query)

        self.params["ids"] = [element_id_to_id(id) for id in self.ids]
