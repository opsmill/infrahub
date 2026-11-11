from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.graph.schema import GraphAttributeValueIndexedNode
from infrahub.core.query import Query, QueryNode, QueryRel, QueryType
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.types import is_large_attribute_type

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryElement
    from infrahub.database import InfrahubDatabase

# Entering from an index reads every edge of the indexed vertices, whatever kind is on the other side,
# so it only replaces the read of every node of the kind when the kind holds this many nodes per edge.
INDEX_START_MIN_KIND_NODES_PER_EDGE = 2

ATTRIBUTE_LIST_KIND = "List"


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


def _is_exact_attribute_value_filter(
    field: AttributeSchema, filter_name: str, filter_value: Any, partial_match: bool
) -> bool:
    if partial_match or field.kind == ATTRIBUTE_LIST_KIND or is_large_attribute_type(field.kind):
        return False
    if filter_name == "value":
        return isinstance(filter_value, str | int | bool)
    return filter_name == "values" and isinstance(filter_value, list)


def _is_peer_id_filter(filter_name: str, filter_value: Any) -> bool:
    if filter_name == "id":
        return isinstance(filter_value, str)
    return filter_name == "ids" and isinstance(filter_value, list)


def _can_start_from_index(
    field: AttributeSchema | RelationshipSchema | None, filter_name: str, filter_value: Any, partial_match: bool
) -> bool:
    if isinstance(field, AttributeSchema):
        return _is_exact_attribute_value_filter(
            field=field, filter_name=filter_name, filter_value=filter_value, partial_match=partial_match
        )
    if isinstance(field, RelationshipSchema):
        return _is_peer_id_filter(filter_name=filter_name, filter_value=filter_value)
    return False


async def find_index_start(
    db: InfrahubDatabase,
    field: AttributeSchema | RelationshipSchema | None,
    name: str,
    filter_name: str,
    filter_value: Any,
    branch: Branch,
    partial_match: bool,
    subquery_idx: int,
    position: int,
) -> IndexStart | None:
    """Return the index start of a filter, or None when the filter cannot be answered from an index.

    The start matches the same path as the filter does, without its branch and time conditions, so it reaches
    every node the filter keeps.
    """
    if field is None or not _can_start_from_index(
        field=field, filter_name=filter_name, filter_value=filter_value, partial_match=partial_match
    ):
        return None

    field_filter, field_params, field_where = await field.get_query_filter(
        db=db,
        name=name,
        include_match=False,
        filter_name=filter_name,
        filter_value=filter_value,
        branch=branch,
        param_prefix=f"filter{subquery_idx}",
        partial_match=partial_match,
    )
    last_edge, indexed_vertex = field_filter[-2], field_filter[-1]
    if not isinstance(last_edge, QueryRel) or not isinstance(indexed_vertex, QueryNode):
        return None
    is_filtered = bool(indexed_vertex.params or field_where)
    is_indexed = isinstance(field, RelationshipSchema) or indexed_vertex.labels == [
        GraphAttributeValueIndexedNode.get_default_label()
    ]
    if not is_filtered or not is_indexed:
        return None

    return IndexStart(
        position=position,
        path=field_filter[:-1],
        last_edge=QueryRel(labels=last_edge.labels, direction=last_edge.direction),
        indexed_vertex=indexed_vertex,
        indexed_vertex_where=field_where,
        params=field_params,
    )


class NodeGetListIndexStartQuery(Query):
    """Count the edges each index start would read, and the nodes of the kind a list query reads without one."""

    name = "node_get_list_index_start"
    type = QueryType.READ

    def __init__(self, node_kind: str, index_starts: list[IndexStart]) -> None:
        # The query returns one row, and a read without a limit is run again until a page comes back short.
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
