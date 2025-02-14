from typing import Any, Generator

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffFieldSpecifiersQuery(Query):
    name = "enriched_diff_field_specifiers"
    type = QueryType.READ

    def __init__(self, diff_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.diff_id = diff_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["diff_id"] = self.diff_id
        query = """
CALL {
    MATCH (root:DiffRoot {uuid: $diff_id})-[:DIFF_HAS_NODE]->(node:DiffNode)-[:DIFF_HAS_ATTRIBUTE]->(attr:DiffAttribute)
    WHERE (root.is_merged IS NULL OR root.is_merged <> TRUE)
    RETURN node.uuid AS node_uuid, attr.name AS field_name
    UNION
    MATCH (root:DiffRoot {uuid: $diff_id})-[:DIFF_HAS_NODE]->(node:DiffNode)-[:DIFF_HAS_RELATIONSHIP]->(rel:DiffRelationship)
    WHERE (root.is_merged IS NULL OR root.is_merged <> TRUE)
    RETURN node.uuid AS node_uuid, rel.identifier AS field_name
}
        """
        self.add_to_query(query=query)
        self.return_labels = ["node_uuid", "field_name"]
        self.order_by = ["node_uuid", "field_name"]

    def get_node_field_specifier_tuples(self) -> Generator[tuple[str, str], None, None]:
        for result in self.get_results():
            node_uuid = result.get_as_str("node_uuid")
            field_name = result.get_as_str("field_name")
            if node_uuid and field_name:
                yield (node_uuid, field_name)
