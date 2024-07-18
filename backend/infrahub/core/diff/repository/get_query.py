from typing import Any, Iterable

from neo4j.graph import Node as Neo4jNode

from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import EnrichedDiffRoot


class EnrichedDiffGetQuery(Query):
    """Get all EnrichedDiffRoots for the given branches that are within the given timeframe in chronological order"""

    name = "enriched_diff_get"
    type = QueryType.READ

    def __init__(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp,
        to_time: Timestamp,
        root_node_uuids: list[str] | None,
        max_depth: int,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.base_branch_name = base_branch_name
        self.diff_branch_names = diff_branch_names
        self.from_time = from_time
        self.to_time = to_time
        self.root_node_uuids = root_node_uuids
        self.max_depth = max_depth

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {
            "base_branch": self.base_branch_name,
            "diff_branches": self.diff_branch_names,
            "from_time": self.from_time.to_string(),
            "to_time": self.to_time.to_string(),
            "root_node_uuids": self.root_node_uuids,
            "limit": self.limit,
            "offset": self.offset,
        }
        # ruff: noqa: E501
        query = """
        // get the roots of all diffs in the query
        MATCH (diff_root:DiffRoot)
        WHERE diff_root.base_branch = $base_branch
        AND diff_root.diff_branch IN $diff_branches
        AND diff_root.from_time >= $from_time
        AND diff_root.to_time <= $to_time
        // get all the nodes attached to the diffs
        OPTIONAL MATCH (diff_root)-[DIFF_HAS_NODE]->(diff_node:DiffNode)
        // if root_node_uuids, filter on uuids
        WHERE ($root_node_uuids IS NULL OR diff_node.uuid in $root_node_uuids)
        // do the pagination
        WITH diff_root, diff_node
        ORDER BY diff_root.diff_branch ASC, diff_root.from_time ASC, diff_node.kind ASC, diff_node.uuid ASC
        SKIP COALESCE($offset, 0)
        LIMIT $limit
        WITH diff_root, diff_node
        // if depth limit, make sure not to exceed it when traversing linked nodes
        WITH diff_root, diff_node, NULL as parent_node
        CALL {
            WITH diff_node
            OPTIONAL MATCH descendant_path = (diff_node) ((parent:DiffNode)-[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)-[:DIFF_HAS_NODE]->(child:DiffNode)){0, %(max_depth)s}
            // turn them into a nested list of the form [[parent node, child node], ...]
            RETURN reduce(pairs = [], i IN range(0, size(parent)- 1) | pairs + [[parent[i], child[i]]]) AS parent_child_pairs
        }
        WITH diff_root, diff_node, parent_node, parent_child_pairs
        WITH diff_root, [[parent_node, diff_node]] + parent_child_pairs AS parent_child_pairs
        UNWIND parent_child_pairs AS parent_child_pair
        WITH diff_root, parent_child_pair[0] AS parent_node, parent_child_pair[1] AS diff_node
        OPTIONAL MATCH (diff_node)-[DIFF_HAS_ATTRIBUTE]->(diff_attribute:DiffAttribute)
                        -[DIFF_HAS_PROPERTY]->(diff_attr_property:DiffProperty)
                        -[DIFF_HAS_CONFLICT]->(diff_attr_conflict:DiffConflict)
        WITH diff_root, diff_node, parent_node, diff_attribute, diff_attr_property, diff_attr_conflict
        OPTIONAL MATCH (diff_node)-[DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship)
                        -[DIFF_HAS_ELEMENT]->(diff_rel_element:DiffRelationshipElement)
                        -[DIFF_HAS_PROPERTY]->(diff_rel_property:DiffProperty)
                        -[DIFF_HAS_CONFLICT]->(diff_rel_conflict:DiffConflict)
        """ % {"max_depth": self.max_depth}
        self.return_labels = [
            "diff_root",
            "diff_node",
            "parent_node",
            "diff_attribute",
            "diff_attr_property",
            "diff_attr_conflict",
            "diff_relationship",
            "diff_rel_element",
            "diff_rel_property",
            "diff_rel_conflict",
        ]
        self.order_by = ["diff_root.diff_branch_name ASC", "diff_root.from_time ASC"]
        self.add_to_query(query=query)

    async def get_enriched_diff_roots(self) -> list[EnrichedDiffRoot]:
        enriched_diffs = await self._deserialize(database_results=self.get_results())
        return enriched_diffs

    async def _deserialize(self, database_results: Iterable[QueryResult]) -> list[EnrichedDiffRoot]:
        diff_root_map: dict[str, EnrichedDiffRoot] = {}
        for result in database_results:
            diff_root_node = result.get_node("diff_root")
            diff_root_uuid = str(diff_root_node.get("uuid"))
            if diff_root_uuid not in diff_root_map:
                diff_root_map[diff_root_uuid] = self._deserialize_diff_root(diff_root_node=diff_root_node)
        return list(diff_root_map.values())

    def _deserialize_diff_root(self, diff_root_node: Neo4jNode) -> EnrichedDiffRoot:
        from_time = Timestamp(str(diff_root_node.get("from_time")))
        to_time = Timestamp(str(diff_root_node.get("to_time")))
        return EnrichedDiffRoot(
            base_branch_name=str(diff_root_node.get("base_branch")),
            diff_branch_name=str(diff_root_node.get("diff_branch")),
            from_time=from_time,
            to_time=to_time,
            uuid=str(diff_root_node.get("uuid")),
        )
