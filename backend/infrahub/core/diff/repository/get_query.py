from typing import Any, Iterable

from infrahub.core.constants import DiffAction
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import EnrichedDiffAttribute, EnrichedDiffNode, EnrichedDiffProperty, EnrichedDiffRoot


class EnrichedDiffGetQuery(Query):
    """Get all EnrichedDiffRoots for the given branches that are within the given timeframe in chronological order"""

    name = "enriched_diff_get"
    type = QueryType.READ
    insert_limit = False

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
        WITH diff_root, parent_node, diff_node, diff_attribute
        OPTIONAL MATCH (diff_attribute)-[DIFF_HAS_PROPERTY]->(diff_attr_property:DiffProperty)
        WITH diff_root, parent_node, diff_node, diff_attribute, diff_attr_property
        OPTIONAL MATCH (diff_attr_property)-[DIFF_HAS_CONFLICT]->(diff_attr_conflict:DiffConflict)
        WITH diff_root, parent_node, diff_node, diff_attribute, diff_attr_property, diff_attr_conflict
        OPTIONAL MATCH (diff_node)-[DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship)
        WITH diff_root, parent_node, diff_node, diff_attribute, diff_attr_property, diff_attr_conflict, diff_relationship
        OPTIONAL MATCH (diff_relationship)-[DIFF_HAS_ELEMENT]->(diff_rel_element:DiffRelationshipElement)
        WITH diff_root, parent_node, diff_node, diff_attribute, diff_attr_property, diff_attr_conflict, diff_relationship, diff_rel_element
        OPTIONAL MATCH (diff_rel_element)-[DIFF_HAS_PROPERTY]->(diff_rel_property:DiffProperty)
        WITH diff_root, parent_node, diff_node, diff_attribute, diff_attr_property, diff_attr_conflict, diff_relationship, diff_rel_element, diff_rel_property
        OPTIONAL MATCH (diff_rel_property)-[DIFF_HAS_CONFLICT]->(diff_rel_conflict:DiffConflict)
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
        deserializer = EnrichedDiffDeserializer()
        enriched_diffs = await deserializer.deserialize(database_results=self.get_results())
        return enriched_diffs


class EnrichedDiffDeserializer:
    def __init__(self) -> None:
        self._diff_root_map: dict[str, EnrichedDiffRoot] = {}
        self._diff_node_map: dict[str, EnrichedDiffNode] = {}
        self._diff_node_attr_map: dict[tuple[str, str], EnrichedDiffAttribute] = {}
        self._diff_prop_map: dict[tuple[str, str, str], EnrichedDiffProperty] = {}

    async def deserialize(self, database_results: Iterable[QueryResult]) -> list[EnrichedDiffRoot]:
        for result in database_results:
            self._deserialize_diff_root(result=result)
            self._deserialize_diff_node(result=result)
            self._deserialize_diff_attr(result=result)
            self._deserialize_diff_attr_property(result=result)

        return list(self._diff_root_map.values())

    def _get_root_key(self, result: QueryResult) -> str:
        diff_root_node = result.get_node("diff_root")
        return str(diff_root_node.get("uuid"))

    def _get_enriched_root(self, result: QueryResult) -> EnrichedDiffRoot:
        root_key = self._get_root_key(result=result)
        return self._diff_root_map[root_key]

    def _get_node_key(self, result: QueryResult) -> str:
        diff_node_node = result.get_node("diff_node")
        return str(diff_node_node.get("uuid"))

    def _get_enriched_node(self, result: QueryResult) -> EnrichedDiffNode:
        node_key = self._get_node_key(result=result)
        return self._diff_node_map[node_key]

    def _get_attribute_key(self, result: QueryResult) -> tuple[str, str] | None:
        diff_attr_node = result.get("diff_attribute")
        if not diff_attr_node:
            return None
        diff_attr_name = str(diff_attr_node.get("name"))
        enriched_node = self._get_enriched_node(result=result)
        return (enriched_node.uuid, diff_attr_name)

    def _get_enriched_attr(self, result: QueryResult) -> EnrichedDiffAttribute:
        attr_key = self._get_attribute_key(result=result)
        if not attr_key:
            raise IndexError(f"No attribute for {attr_key}")
        return self._diff_node_attr_map[attr_key]

    def _get_attribute_property_key(self, result: QueryResult) -> tuple[str, str, str] | None:
        diff_attr_prop_node = result.get("diff_attr_property")
        if not diff_attr_prop_node:
            return None
        diff_prop_type = str(diff_attr_prop_node.get("property_type"))
        enriched_node = self._get_enriched_node(result=result)
        enriched_attr = self._get_enriched_attr(result=result)
        return (enriched_node.uuid, enriched_attr.name, diff_prop_type)

    def _deserialize_diff_root(self, result: QueryResult) -> None:
        root_key = self._get_root_key(result=result)
        if root_key in self._diff_root_map:
            return

        diff_root_node = result.get_node("diff_root")
        diff_root_uuid = str(diff_root_node.get("uuid"))
        from_time = Timestamp(str(diff_root_node.get("from_time")))
        to_time = Timestamp(str(diff_root_node.get("to_time")))
        enriched_root = EnrichedDiffRoot(
            base_branch_name=str(diff_root_node.get("base_branch")),
            diff_branch_name=str(diff_root_node.get("diff_branch")),
            from_time=from_time,
            to_time=to_time,
            uuid=str(diff_root_uuid),
        )
        self._diff_root_map[root_key] = enriched_root
        return

    def _deserialize_diff_node(self, result: QueryResult) -> None:
        node_key = self._get_node_key(result=result)
        if node_key in self._diff_node_map:
            return

        diff_node_node = result.get_node("diff_node")
        diff_node_uuid = str(diff_node_node.get("uuid"))
        enriched_node = EnrichedDiffNode(
            uuid=diff_node_uuid,
            kind=str(diff_node_node.get("kind")),
            label=str(diff_node_node.get("label")),
            changed_at=Timestamp(diff_node_node.get("changed_at")),
            action=DiffAction(str(diff_node_node.get("action"))),
        )
        self._diff_node_map[node_key] = enriched_node
        enriched_root = self._get_enriched_root(result=result)
        enriched_root.nodes.append(enriched_node)
        return

    def _deserialize_diff_attr(self, result: QueryResult) -> None:
        attr_key = self._get_attribute_key(result=result)
        if attr_key is None:
            return
        if attr_key in self._diff_node_attr_map:
            return

        diff_attr_node = result.get_node("diff_attribute")
        diff_attribute = EnrichedDiffAttribute(
            name=str(diff_attr_node.get("name")),
            changed_at=Timestamp(str(diff_attr_node.get("changed_at"))),
            action=DiffAction(str(diff_attr_node.get("action"))),
        )
        self._diff_node_attr_map[attr_key] = diff_attribute
        enriched_node = self._get_enriched_node(result=result)
        enriched_node.attributes.append(diff_attribute)
        return

    def _deserialize_diff_attr_property(self, result: QueryResult) -> None:
        attr_property_key = self._get_attribute_property_key(result=result)
        if attr_property_key is None:
            return
        if attr_property_key in self._diff_prop_map:
            return

        diff_attr_prop_node = result.get_node("diff_attr_property")

        previous_value_raw = diff_attr_prop_node.get("previous_value")
        previous_value = str(previous_value_raw) if previous_value_raw is not None else None
        new_value_raw = diff_attr_prop_node.get("new_value")
        new_value = str(new_value_raw) if new_value_raw is not None else None
        enriched_property = EnrichedDiffProperty(
            property_type=str(diff_attr_prop_node.get("property_type")),
            changed_at=Timestamp(str(diff_attr_prop_node.get("changed_at"))),
            previous_value=previous_value,
            new_value=new_value,
            action=DiffAction(str(diff_attr_prop_node.get("action"))),
            conflict=None,
        )
        enriched_attr = self._get_enriched_attr(result=result)
        enriched_attr.properties.append(enriched_property)
        self._diff_prop_map[attr_property_key] = enriched_property
