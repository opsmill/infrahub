from typing import Any

from infrahub.core.diff.model.path import NodeIdentifier
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffDropNodesQuery(Query):
    name = "enriched_diff_drop_nodes"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, enriched_diff_uuid: str, node_identifiers: list[NodeIdentifier], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.enriched_diff_uuid = enriched_diff_uuid
        self.node_identifiers = node_identifiers

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_root_uuid": self.enriched_diff_uuid,
            "node_uuids": [ni.uuid for ni in self.node_identifiers],
            "node_identifiers_map": {ni.uuid: ni.kind for ni in self.node_identifiers},
        }
        query = """
        MATCH (d_root:DiffRoot {uuid: $diff_root_uuid})
        MATCH (d_root)-[:DIFF_HAS_NODE]->(dn:DiffNode)
        WHERE dn.uuid IN $node_uuids
        AND dn.kind IN $node_identifiers_map[dn.uuid]
        OPTIONAL MATCH (dn)-[:DIFF_HAS_ATTRIBUTE]-(da:DiffAttribute)
        OPTIONAL MATCH (da)-[*]->(diff_thing)
        DETACH DELETE diff_thing
        DETACH DELETE da
        WITH dn
        OPTIONAL MATCH (dn)-[:DIFF_HAS_RELATIONSHIP]->(dr:DiffRelationship)
        OPTIONAL MATCH (dr)-[:DIFF_HAS_ELEMENT]->(dre:DiffRelationshipElement)
        OPTIONAL MATCH (dre)-[*]->(diff_thing)
        DETACH DELETE diff_thing
        DETACH DELETE dre
        DETACH DELETE dr
        DETACH DELETE dn
        """
        self.add_to_query(query=query)
