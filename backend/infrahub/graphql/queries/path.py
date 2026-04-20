from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Enum, Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphql import GraphQLError

from infrahub.core.manager import NodeManager
from infrahub.core.query.path import PathTraversalQuery

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class PathDirectionEnum(Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIR = "bidirectional"


class PathNodeType(ObjectType):
    id = Field(String, required=True, description="Node UUID")
    kind = Field(String, required=True, description="Schema kind")
    display_label = Field(String, required=True, description="Human-readable display label")


class PathRelationshipType(ObjectType):
    id = Field(String, required=True, description="Relationship UUID")
    name = Field(String, required=True, description="Relationship name")
    direction = Field(PathDirectionEnum, required=True, description="Direction relative to traversal")


class PathResultType(ObjectType):
    nodes = Field(
        List(of_type=NonNull(PathNodeType)), required=True, description="Ordered nodes from source to destination"
    )
    relationships = Field(
        List(of_type=NonNull(PathRelationshipType)),
        required=True,
        description="Ordered relationships connecting the nodes",
    )
    depth = Field(Int, required=True, description="Number of node hops in this path")


class PathTraversalResultType(ObjectType):
    paths = Field(
        List(of_type=NonNull(PathResultType)), required=True, description="Paths found, ordered shortest first"
    )
    source = Field(PathNodeType, required=True, description="The start node")
    destination = Field(PathNodeType, required=True, description="The end node")
    total_paths_found = Field(Int, required=True, description="Total number of paths discovered")


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


def _path_data_to_result(path_data: Any, display_labels: dict[str, str]) -> dict[str, Any]:
    nodes = [
        {"id": n.uuid, "kind": n.kind, "display_label": display_labels.get(n.uuid, n.kind)} for n in path_data.nodes
    ]
    relationships = [{"id": r.uuid, "name": r.name, "direction": r.direction.value} for r in path_data.relationships]
    return {"nodes": nodes, "relationships": relationships, "depth": path_data.depth}


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

    source_node = await NodeManager.get_one(
        db=graphql_context.db,
        branch=graphql_context.branch,
        at=graphql_context.at,
        id=source_id,
    )
    if not source_node:
        raise GraphQLError(f"Source node not found: {source_id}")

    destination_node = await NodeManager.get_one(
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

    all_node_ids: set[str] = set()
    for path_data in path_data_list:
        all_node_ids.update(n.uuid for n in path_data.nodes)

    display_labels: dict[str, str] = {}
    if all_node_ids:
        loaded_nodes = await NodeManager.get_many(
            db=graphql_context.db,
            branch=graphql_context.branch,
            at=graphql_context.at,
            ids=list(all_node_ids),
        )
        for node_id, node in loaded_nodes.items():
            display_labels[node_id] = await node.get_display_label(db=graphql_context.db)

    source_info = {
        "id": source_node.id,
        "kind": source_node.get_kind(),
        "display_label": display_labels.get(source_id, source_node.get_kind()),
    }
    destination_info = {
        "id": destination_node.id,
        "kind": destination_node.get_kind(),
        "display_label": display_labels.get(destination_id, destination_node.get_kind()),
    }

    paths = [_path_data_to_result(p, display_labels) for p in path_data_list]

    return {
        "paths": paths,
        "source": source_info,
        "destination": destination_info,
        "total_paths_found": len(path_data_list),
    }


InfrahubPathTraversal = Field(
    PathTraversalResultType,
    data=PathTraversalInput(required=True),
    description="Find all shortest paths between two nodes in the graph",
    resolver=path_traversal_resolver,
    required=True,
)
