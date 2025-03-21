from typing import Any, Generator

from neo4j.graph import Node as Neo4jNode

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import TrackingId


class EnrichedDiffAllConflictsQuery(Query):
    name = "enriched_diff_all_conflicts"
    type = QueryType.READ

    def __init__(
        self, diff_branch_name: str, tracking_id: TrackingId | None = None, diff_id: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        if (diff_id is None and tracking_id is None) or (diff_id and tracking_id):
            raise ValueError("EnrichedDiffAllConflictsQuery requires one and only one of `tracking_id` or `diff_id`")
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id
        self.diff_id = diff_id
        if self.tracking_id is None and self.diff_id is None:
            raise RuntimeError("tracking_id or diff_id is required")

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_name": self.diff_branch_name,
            "diff_id": self.diff_id,
            "tracking_id": self.tracking_id.serialize() if self.tracking_id else None,
        }
        query = """
MATCH (root:DiffRoot)
WHERE (root.is_merged IS NULL OR root.is_merged <> TRUE)
AND (
    ($diff_id IS NOT NULL AND root.uuid = $diff_id)
    OR ($tracking_id IS NOT NULL AND root.tracking_id = $tracking_id AND root.diff_branch = $diff_branch_name)
)
CALL {
    WITH root
    MATCH (root)-[:DIFF_HAS_NODE]->(node:DiffNode)-[:DIFF_HAS_CONFLICT]->(node_conflict:DiffConflict)
    RETURN node.path_identifier AS path_identifier, node_conflict AS conflict
    UNION
    WITH root
    MATCH (root)-[:DIFF_HAS_NODE]->(node:DiffNode)-[:DIFF_HAS_ATTRIBUTE]->(:DiffAttribute)
        -[:DIFF_HAS_PROPERTY]->(property:DiffProperty)-[:DIFF_HAS_CONFLICT]->(attr_property_conflict:DiffConflict)
    RETURN property.path_identifier AS path_identifier, attr_property_conflict AS conflict
    UNION
    WITH root
    MATCH (root)-[:DIFF_HAS_NODE]->(node:DiffNode)-[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)
        -[:DIFF_HAS_ELEMENT]->(element:DiffRelationshipElement)-[:DIFF_HAS_CONFLICT]->(rel_element_conflict:DiffConflict)
    RETURN element.path_identifier AS path_identifier, rel_element_conflict AS conflict
    UNION
    WITH root
    MATCH (root)-[:DIFF_HAS_NODE]->(node:DiffNode)-[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)
        -[:DIFF_HAS_ELEMENT]->(:DiffRelationshipElement)-[:DIFF_HAS_PROPERTY]->(property:DiffProperty)
        -[:DIFF_HAS_CONFLICT]->(rel_property_conflict:DiffConflict)
    RETURN property.path_identifier AS path_identifier, rel_property_conflict AS conflict
}
"""
        self.return_labels = ["path_identifier", "conflict"]
        self.add_to_query(query=query)

    def get_conflict_paths_and_nodes(self) -> Generator[tuple[str, Neo4jNode], None, None]:
        for result in self.get_results():
            yield (result.get_as_type("path_identifier", str), result.get_node("conflict"))
