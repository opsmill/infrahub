from typing import Any, Generator

from neo4j.graph import Node as Neo4jNode

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffEmptyRootsQuery(Query):
    name = "enriched_diff_empty_roots"
    type = QueryType.READ

    def __init__(
        self, diff_branch_names: list[str] | None = None, base_branch_names: list[str] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.diff_branch_names = diff_branch_names
        self.base_branch_names = base_branch_names

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {"diff_branch_names": self.diff_branch_names, "base_branch_names": self.base_branch_names}

        query = """
        MATCH (diff_root:DiffRoot)
        WHERE ($diff_branch_names IS NULL OR diff_root.diff_branch IN $diff_branch_names)
        AND ($base_branch_names IS NULL OR diff_root.base_branch IN $base_branch_names)
        """
        self.return_labels = ["diff_root"]
        self.add_to_query(query=query)

    def get_empty_root_nodes(self) -> Generator[Neo4jNode, None, None]:
        for result in self.get_results():
            yield result.get_node("diff_root")
