from typing import Any, Generator

from neo4j.graph import Node as Neo4jNode

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffEmptyRootsQuery(Query):
    name = "enriched_diff_empty_roots"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        query = """
        MATCH (diff_root:DiffRoot)
        """
        self.return_labels = ["diff_root"]
        self.add_to_query(query=query)

    def get_empty_root_nodes(self) -> Generator[Neo4jNode, None, None]:
        for result in self.get_results():
            yield result.get_node("diff_root")
