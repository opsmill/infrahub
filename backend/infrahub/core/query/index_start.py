from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipDirection
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.constants.relationship_label import RELATIONSHIP_TO_NODE_LABEL, RELATIONSHIP_TO_VALUE_LABEL
from infrahub.core.graph.schema import GraphAttributeValueIndexedNode
from infrahub.core.query import Query, QueryElement, QueryNode, QueryRel, QueryRelDirection, QueryType
from infrahub.core.query.node_get_list_filters import get_filter_requirements
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.types import is_large_attribute_type

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes

# A start from an index reads every edge of the indexed vertices, whatever kind is on the other side; in query
# profiles that reads more than a read of every node of the kind at one node per edge, and less at two.
INDEX_START_MIN_KIND_NODES_PER_EDGE = 2

# The edges around a Relationship vertex point the way the relationship does, so the path to the peer follows them.
PEER_PATH_DIRECTIONS: dict[RelationshipDirection, tuple[QueryRelDirection, QueryRelDirection]] = {
    RelationshipDirection.BIDIR: (QueryRelDirection.OUTBOUND, QueryRelDirection.INBOUND),
    RelationshipDirection.OUTBOUND: (QueryRelDirection.OUTBOUND, QueryRelDirection.OUTBOUND),
    RelationshipDirection.INBOUND: (QueryRelDirection.INBOUND, QueryRelDirection.INBOUND),
}


@dataclass(frozen=True)
class IndexStart:
    """A filter whose path a list query can enter from its indexed end instead of from every node of the kind."""

    position: int
    path: list[QueryElement]
    last_edge: QueryRel
    indexed_vertex: QueryNode
    indexed_vertex_where: list[str]
    params: dict[str, Any]

    @property
    def edges_variable(self) -> str:
        return f"index_start{self.position}_edges"

    @property
    def indexed_vertex_match(self) -> str:
        if not self.indexed_vertex_where:
            return f"MATCH {self.indexed_vertex}"
        return f"MATCH {self.indexed_vertex}\nWHERE {' AND '.join(self.indexed_vertex_where)}"

    @property
    def path_to_indexed_vertex(self) -> str:
        return "".join(str(item) for item in self.path)


def _is_list_of_scalars(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str | int | bool) for item in value)


def _build_attribute_value_start(
    field: AttributeSchema, filter_name: str, filter_value: Any, position: int
) -> IndexStart | None:
    if is_large_attribute_type(field.kind):
        return None

    value = field.convert_enum_to_value(filter_value) if field.enum else filter_value
    prefix = f"index_start{position}"
    indexed_vertex = QueryNode(name="av", labels=[GraphAttributeValueIndexedNode.get_default_label()])
    indexed_vertex_where: list[str] = []
    if filter_name == "value" and isinstance(value, str | int | bool):
        indexed_vertex.params = {"value": f"${prefix}_value"}
    elif filter_name == "values" and _is_list_of_scalars(value):
        indexed_vertex_where.append(f"{indexed_vertex.name}.value IN ${prefix}_value")
    else:
        return None

    return IndexStart(
        position=position,
        path=[
            QueryRel(labels=[RELATIONSHIP_TO_NODE_LABEL]),
            QueryNode(name="i", labels=["Attribute"], params={"name": f"${prefix}_name"}),
            QueryRel(labels=[RELATIONSHIP_TO_VALUE_LABEL]),
        ],
        last_edge=QueryRel(labels=[RELATIONSHIP_TO_VALUE_LABEL]),
        indexed_vertex=indexed_vertex,
        indexed_vertex_where=indexed_vertex_where,
        params={f"{prefix}_name": field.name, f"{prefix}_value": value},
    )


def _build_peer_start(
    field: RelationshipSchema, filter_name: str, filter_value: Any, position: int
) -> IndexStart | None:
    prefix = f"index_start{position}"
    indexed_vertex = QueryNode(name="peer", labels=["Node"])
    indexed_vertex_where: list[str] = []
    params: dict[str, Any] = {f"{prefix}_rel_name": field.get_identifier()}
    if filter_name == "id" and isinstance(filter_value, str):
        indexed_vertex.params = {"uuid": f"${prefix}_peer_id"}
        params[f"{prefix}_peer_id"] = filter_value
    elif filter_name == "ids" and isinstance(filter_value, list):
        indexed_vertex_where.append(f"{indexed_vertex.name}.uuid IN ${prefix}_peer_ids")
        params[f"{prefix}_peer_ids"] = filter_value
    else:
        return None

    edge_label = DatabaseEdgeType.IS_RELATED.value
    to_relationship, to_peer = PEER_PATH_DIRECTIONS[field.direction]
    return IndexStart(
        position=position,
        path=[
            QueryRel(name="r1", labels=[edge_label], direction=to_relationship),
            QueryNode(name="rl", labels=["Relationship"], params={"name": f"${prefix}_rel_name"}),
            QueryRel(name="r2", labels=[edge_label], direction=to_peer),
        ],
        last_edge=QueryRel(labels=[edge_label], direction=to_peer),
        indexed_vertex=indexed_vertex,
        indexed_vertex_where=indexed_vertex_where,
        params=params,
    )


def build_index_start(
    field: AttributeSchema | RelationshipSchema | None,
    filter_name: str,
    filter_value: Any,
    partial_match: bool,
    position: int,
) -> IndexStart | None:
    """Return the index start of a filter, or None when the filter cannot be answered from an index.

    An exact value of an attribute whose values are indexed qualifies, and so do the ids of the peers of a
    relationship. The start has no branch or time condition, so it reaches every node the filter keeps.
    """
    if isinstance(field, AttributeSchema) and not partial_match:
        return _build_attribute_value_start(
            field=field, filter_name=filter_name, filter_value=filter_value, position=position
        )
    if isinstance(field, RelationshipSchema):
        return _build_peer_start(field=field, filter_name=filter_name, filter_value=filter_value, position=position)
    return None


def get_index_starts(schema: MainSchemaTypes, filters: dict[str, Any] | None, partial_match: bool) -> list[IndexStart]:
    """Return the index start of each filter of a list read that has one, none when the read filters on node ids."""
    if not filters or "id" in filters or "ids" in filters:
        return []

    index_starts: list[IndexStart] = []
    for requirement in get_filter_requirements(schema=schema, filters=filters, partial_match=partial_match):
        if requirement.is_metadata:
            continue
        index_start = build_index_start(
            field=requirement.field,
            filter_name=requirement.field_attr_name,
            filter_value=requirement.field_attr_value,
            partial_match=partial_match,
            position=len(index_starts) + 1,
        )
        if index_start:
            index_starts.append(index_start)
    return index_starts


class NodeGetListIndexStartQuery(Query):
    """Count the edges each index start would read, and the nodes of the kind a list query reads without one."""

    name = "node_get_list_index_start"
    type = QueryType.READ

    def __init__(self, node_kind: str, index_starts: list[IndexStart]) -> None:
        # One row comes back, and a read without a limit is sent a second time when a page holds one row.
        super().__init__(limit=1)
        self.index_starts = index_starts

        query = """
        CALL () {
            MATCH (kind_node:%(node_kind)s)
            RETURN count(kind_node) AS kind_count
        }
        """ % {"node_kind": node_kind}
        self.add_to_query(query)
        self.return_labels = ["kind_count"]

        for index_start in self.index_starts:
            self.params.update(index_start.params)
            query = """
            CALL () {
                %(indexed_vertex_match)s
                RETURN sum(COUNT { ()%(last_edge)s(%(indexed_vertex)s) }) AS %(edges_variable)s
            }
            """ % {
                "indexed_vertex_match": index_start.indexed_vertex_match,
                "last_edge": index_start.last_edge,
                "indexed_vertex": index_start.indexed_vertex.name,
                "edges_variable": index_start.edges_variable,
            }
            self.add_to_query(query)
            self.return_labels.append(index_start.edges_variable)

    def get_selected_index_start(self) -> IndexStart | None:
        """Return the index start that reads the fewest edges, or None when reading every node of the kind costs less."""
        result = self.get_result()
        if result is None:
            return None

        kind_count = result.get_as_type("kind_count", return_type=int)
        edges_by_position = {
            index_start.position: result.get_as_type(index_start.edges_variable, return_type=int)
            for index_start in self.index_starts
        }
        cheapest = min(self.index_starts, key=lambda index_start: edges_by_position[index_start.position])
        if edges_by_position[cheapest.position] * INDEX_START_MIN_KIND_NODES_PER_EDGE > kind_count:
            return None
        return cheapest
