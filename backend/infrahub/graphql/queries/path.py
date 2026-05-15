from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphql import GraphQLError

from infrahub.core.manager import NodeManager
from infrahub.exceptions import SchemaNotFoundError
from infrahub.graph_traversal.path import PathData, PathTraversalQuery

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.graphql.initialization import GraphqlContext


class PathNodeType(ObjectType):
    id = Field(String, required=True, description="Node UUID")
    kind = Field(String, required=True, description="Schema kind")
    label = Field(String, required=True, description="Schema label for the node's kind")
    display_label = Field(String, required=True, description="Human-readable display label")
    hfid = Field(List(of_type=NonNull(String)), required=True, description="Human friendly identifier")


class PathRelationshipType(ObjectType):
    from_rel = Field(String, required=True, description="Relationship name on the source side of the hop")
    from_label = Field(String, required=True, description="Relationship label on the source side of the hop")
    to_rel = Field(String, required=True, description="Relationship name on the destination side of the hop")
    to_label = Field(String, required=True, description="Relationship label on the destination side of the hop")
    kind = Field(String, required=True, description="Relationship kind (e.g. Component, Generic)")


class PathHopType(ObjectType):
    node = Field(PathNodeType, required=True, description="Node visited at this hop")
    relationship = Field(
        PathRelationshipType,
        required=False,
        description="Relationship traversed to reach this node from the previous hop. Null on the first hop.",
    )


class PathResultType(ObjectType):
    hops = Field(
        List(of_type=NonNull(PathHopType)), required=True, description="Ordered hops from source to destination"
    )
    depth = Field(Int, required=True, description="Number of edges in this path")


class PathTraversalResultType(ObjectType):
    paths = Field(
        List(of_type=NonNull(PathResultType)), required=True, description="Paths found, ordered shortest first"
    )
    source = Field(PathNodeType, required=True, description="The start node")
    destination = Field(PathNodeType, required=True, description="The end node")
    count = Field(Int, required=True, description="Total number of paths discovered")


class PathTraversalInput(InputObjectType):
    source_id = String(required=True, description="UUID of the start node")
    destination_id = String(required=True, description="UUID of the end node")
    max_depth = Int(required=False, default_value=5, description="Maximum number of node hops (default: 5, max: 20)")
    max_paths = Int(
        required=False, default_value=10, description="Maximum number of paths to return (default: 10, max: 100)"
    )
    kind_filter = List(
        of_type=NonNull(String), required=False, description="Filter to only traverse through nodes of these kinds"
    )
    relationship_filter = List(
        of_type=NonNull(String), required=False, description="Filter to only follow relationships with these names"
    )
    excluded_namespaces = List(
        of_type=NonNull(String),
        required=False,
        description="Namespaces to exclude from traversal. Pass empty list to include all.",
    )
    excluded_kinds = List(
        of_type=NonNull(String),
        required=False,
        description="Specific node kinds to exclude from traversal paths.",
    )
    allow_schema_revisits = Boolean(
        required=False,
        default_value=False,
        description=(
            "If false (default), routes that revisit the same schema kind are excluded — "
            "a route's intermediate kinds must be distinct, with the single exception that "
            "the source kind may also be the terminal kind (for same-kind source/target queries). "
            "If true, the planner emits all paths bounded only by max_depth, allowing kinds "
            "to repeat anywhere along a route."
        ),
    )


async def _get_node_labels(graphql_context: GraphqlContext, node_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Load nodes by id and return per-uuid {label, display_label, hfid}.

    `label` is the schema-level label for the node's kind; `display_label` is
    the per-node rendering; `hfid` is the stored human-friendly id list.
    """
    labels_map: dict[str, dict[str, Any]] = {}
    if not node_ids:
        return labels_map

    loaded_nodes = await NodeManager.get_many(
        db=graphql_context.db,
        branch=graphql_context.branch,
        at=graphql_context.at,
        ids=list(node_ids),
    )

    schema_label_cache: dict[str, str] = {}
    for node_id, node in loaded_nodes.items():
        kind = node.get_kind()
        if kind not in schema_label_cache:
            schema_label_cache[kind] = _schema_label_for_kind(graphql_context=graphql_context, kind=kind)
        labels_map[node_id] = {
            "label": schema_label_cache[kind],
            "display_label": await node.get_display_label(db=graphql_context.db),
            "hfid": (await node.get_hfid(db=graphql_context.db)) or [],
        }
    return labels_map


def _schema_label_for_kind(graphql_context: GraphqlContext, kind: str) -> str:
    try:
        node_schema: MainSchemaTypes = graphql_context.db.schema.get(
            name=kind, branch=graphql_context.branch, duplicate=False
        )
    except SchemaNotFoundError:
        return kind
    return node_schema.label or kind


def _node_payload(node_id: str, kind: str, labels_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    meta = labels_map.get(node_id, {})
    return {
        "id": node_id,
        "kind": kind,
        "label": meta.get("label", kind),
        "display_label": meta.get("display_label", kind),
        "hfid": meta.get("hfid", []),
    }


def _resolve_relationship(
    graphql_context: GraphqlContext, identifier: str, from_kind: str, to_kind: str
) -> dict[str, str]:
    """Project a hop's relationship identifier into bidirectional API fields.

    Look up the schema for both endpoints and find the RelationshipSchema with
    the given identifier on each side. Falls back to the identifier when schema
    lookup fails (e.g. legacy data or unknown kinds).
    """
    from_rel_name = identifier
    from_label = identifier
    to_rel_name = identifier
    to_label = identifier
    kind = ""

    with contextlib.suppress(SchemaNotFoundError):
        from_schema: MainSchemaTypes = graphql_context.db.schema.get(
            name=from_kind, branch=graphql_context.branch, duplicate=False
        )
        from_rel = from_schema.get_relationship_by_identifier(id=identifier, raise_on_error=False)
        if from_rel is not None:
            from_rel_name = from_rel.name
            from_label = from_rel.label or from_rel.name
            kind = from_rel.kind.value if hasattr(from_rel.kind, "value") else str(from_rel.kind)

    with contextlib.suppress(SchemaNotFoundError):
        to_schema: MainSchemaTypes = graphql_context.db.schema.get(
            name=to_kind, branch=graphql_context.branch, duplicate=False
        )
        to_rel = to_schema.get_relationship_by_identifier(id=identifier, raise_on_error=False)
        if to_rel is not None:
            to_rel_name = to_rel.name
            to_label = to_rel.label or to_rel.name
            if not kind:
                kind = to_rel.kind.value if hasattr(to_rel.kind, "value") else str(to_rel.kind)

    return {
        "from_rel": from_rel_name,
        "from_label": from_label,
        "to_rel": to_rel_name,
        "to_label": to_label,
        "kind": kind,
    }


def _path_data_to_result(
    path_data: PathData, labels_map: dict[str, dict[str, Any]], graphql_context: GraphqlContext
) -> dict[str, Any]:
    hops: list[dict[str, Any]] = []
    previous_kind: str | None = None
    for hop in path_data.hops:
        node_payload = _node_payload(node_id=hop.node.uuid, kind=hop.node.kind, labels_map=labels_map)
        relationship_payload: dict[str, str] | None = None
        if hop.relationship_identifier is not None and previous_kind is not None:
            relationship_payload = _resolve_relationship(
                graphql_context=graphql_context,
                identifier=hop.relationship_identifier,
                from_kind=previous_kind,
                to_kind=hop.node.kind,
            )
        hops.append({"node": node_payload, "relationship": relationship_payload})
        previous_kind = hop.node.kind

    return {"hops": hops, "depth": path_data.depth}


async def path_traversal_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    data: PathTraversalInput,
) -> dict[str, Any]:
    graphql_context: GraphqlContext = info.context

    source_id = data.source_id
    destination_id = data.destination_id
    max_depth = data.max_depth or 5
    max_paths = data.max_paths or 10
    kind_filter = list(data.kind_filter) if data.kind_filter else []
    relationship_filter = list(data.relationship_filter) if data.relationship_filter else []
    excluded_namespaces = list(data.excluded_namespaces) if data.excluded_namespaces is not None else None
    excluded_kinds = list(data.excluded_kinds) if data.excluded_kinds else []

    if source_id == destination_id:
        raise GraphQLError("Source and destination nodes must be different")

    source_node: Node | None = await NodeManager.get_one(
        db=graphql_context.db,
        branch=graphql_context.branch,
        at=graphql_context.at,
        id=source_id,
    )
    if not source_node:
        raise GraphQLError(f"Source node not found: {source_id}")

    destination_node: Node | None = await NodeManager.get_one(
        db=graphql_context.db,
        branch=graphql_context.branch,
        at=graphql_context.at,
        id=destination_id,
    )
    if not destination_node:
        raise GraphQLError(f"Destination node not found: {destination_id}")

    try:
        query = await PathTraversalQuery.init(
            db=graphql_context.db,
            branch=graphql_context.branch,
            at=graphql_context.at,
            source_id=source_id,
            destination_id=destination_id,
            max_depth=max_depth,
            max_paths=max_paths,
            kind_filter=kind_filter,
            relationship_filter=relationship_filter,
            excluded_namespaces=excluded_namespaces,
            excluded_kinds=excluded_kinds,
        )
        await query.execute(db=graphql_context.db)
    except ValueError as exc:
        raise GraphQLError(str(exc)) from exc

    path_data_list = query.get_paths()

    all_node_ids: set[str] = {source_id, destination_id}
    for path_data in path_data_list:
        all_node_ids.update(hop.node.uuid for hop in path_data.hops)

    labels_map = await _get_node_labels(graphql_context=graphql_context, node_ids=all_node_ids)

    source_info = _node_payload(node_id=source_node.id, kind=source_node.get_kind(), labels_map=labels_map)
    destination_info = _node_payload(
        node_id=destination_node.id, kind=destination_node.get_kind(), labels_map=labels_map
    )

    paths = [_path_data_to_result(p, labels_map, graphql_context) for p in path_data_list]

    return {
        "paths": paths,
        "source": source_info,
        "destination": destination_info,
        "count": len(path_data_list),
    }


InfrahubPathTraversal = Field(
    PathTraversalResultType,
    data=PathTraversalInput(required=True),
    description="Find all shortest paths between two nodes in the graph",
    resolver=path_traversal_resolver,
    required=True,
)
