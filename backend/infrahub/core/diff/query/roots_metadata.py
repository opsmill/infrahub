from typing import Any, Generator

from neo4j.graph import Node as Neo4jNode

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import TrackingId


class EnrichedDiffRootsMetadataQuery(Query):
    name = "enriched_diff_roots_metadata"
    type = QueryType.READ

    def __init__(
        self,
        diff_branch_names: list[str] | None = None,
        base_branch_names: list[str] | None = None,
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        tracking_id: TrackingId | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.diff_branch_names = diff_branch_names
        self.base_branch_names = base_branch_names
        self.from_time = from_time
        self.to_time = to_time
        self.tracking_id = tracking_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_names": self.diff_branch_names,
            "base_branch_names": self.base_branch_names,
            "from_time": self.from_time.to_string() if self.from_time else None,
            "to_time": self.to_time.to_string() if self.to_time else None,
            "tracking_id": self.tracking_id.serialize() if self.tracking_id else None,
        }

        query = """
        MATCH (diff_root:DiffRoot)
        WHERE (diff_root.is_merged IS NULL OR diff_root.is_merged <> TRUE)
        AND ($diff_branch_names IS NULL OR diff_root.diff_branch IN $diff_branch_names)
        AND ($base_branch_names IS NULL OR diff_root.base_branch IN $base_branch_names)
        AND ($from_time IS NULL OR diff_root.from_time >= $from_time)
        AND ($to_time IS NULL OR diff_root.to_time <= $to_time)
        AND ($tracking_id IS NULL OR diff_root.tracking_id = $tracking_id)
        """
        self.return_labels = ["diff_root"]
        self.add_to_query(query=query)

    def get_root_nodes_metadata(self) -> Generator[Neo4jNode, None, None]:
        for result in self.get_results():
            yield result.get_node("diff_root")
