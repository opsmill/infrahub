from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphql import GraphQLError

from infrahub.core.manager import NodeManager
from infrahub.core.query.reachable import ReachableNodesQuery
from infrahub.graphql.queries.path import PathNodeType, PathResultType, _path_data_to_result

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class ReachableNodeType(ObjectType):
    id = Field(String, required=True, description="Node UUID")
    kind = Field(String, required=True, description="Schema kind")
    display_label = Field(String, required=True, description="Human-readable display label")
    depth = Field(Int, required=True, description="Hops from source node")
    relationship_name = Field(String, required=True, description="Relationship connecting this node")
    path = Field(PathResultType, required=True, description="Full path from source to this node")


class ReachableNodesResultType(ObjectType):
    source = Field(PathNodeType, required=True, description="The source node")
    reachable_nodes = Field(
        List(of_type=NonNull(ReachableNodeType)),
        required=True,
        description="Nodes of the requested kinds reachable from the source",
    )
    paths = Field(List(of_type=NonNull(PathResultType)), required=True, description="All paths to reachable nodes")
    total_found = Field(Int, required=True, description="Total reachable nodes found")


class ReachableNodesInput(InputObjectType):
    source_id = String(required=True, description="UUID of the source node")
    target_kinds = List(of_type=NonNull(String), required=True, description="Node kinds to search for")
    max_depth = Int(required=False, default_value=5, description="Maximum traversal depth (default: 5, max: 20)")
    max_results = Int(required=False, default_value=50, description="Maximum results (default: 50, max: 200)")


async def reachable_nodes_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    data: ReachableNodesInput,
) -> dict[str, Any]:
    graphql_context: GraphqlContext = info.context

    source_id = data.source_id
    target_kinds = list(data.target_kinds) if data.target_kinds else []
    max_depth = data.max_depth or 5
    max_results = data.max_results or 50

    source_node = await NodeManager.get_one(
        db=graphql_context.db,
        branch=graphql_context.branch,
        at=graphql_context.at,
        id=source_id,
    )
    if not source_node:
        raise GraphQLError(f"Source node not found: {source_id}")

    try:
        query = await ReachableNodesQuery.init(
            db=graphql_context.db,
            branch=graphql_context.branch,
            at=graphql_context.at,
            source_id=source_id,
            target_kinds=target_kinds,
            max_depth=max_depth,
            max_results=max_results,
        )
        await query.execute(db=graphql_context.db)
    except ValueError as exc:
        raise GraphQLError(str(exc)) from exc

    reachable_data = query.get_reachable_nodes()

    all_ids: set[str] = set()
    for n in reachable_data:
        all_ids.add(n.uuid)
        all_ids.update(pn.uuid for pn in n.path.nodes)

    display_labels: dict[str, str] = {}
    if all_ids:
        loaded_nodes = await NodeManager.get_many(
            db=graphql_context.db,
            branch=graphql_context.branch,
            at=graphql_context.at,
            ids=list(all_ids),
        )
        for node_id, node in loaded_nodes.items():
            display_labels[node_id] = await node.get_display_label(db=graphql_context.db)

    source_info = {
        "id": source_node.id,
        "kind": source_node.get_kind(),
        "display_label": display_labels.get(source_id, await source_node.get_display_label(db=graphql_context.db)),
    }

    reachable_nodes = []
    paths = []
    for n in reachable_data:
        path_result = _path_data_to_result(n.path, display_labels)
        reachable_nodes.append(
            {
                "id": n.uuid,
                "kind": n.kind,
                "display_label": display_labels.get(n.uuid, n.kind),
                "depth": n.depth,
                "relationship_name": n.relationship_name,
                "path": path_result,
            }
        )
        paths.append(path_result)

    return {
        "source": source_info,
        "reachable_nodes": reachable_nodes,
        "paths": paths,
        "total_found": len(reachable_nodes),
    }


InfrahubReachableNodes = Field(
    ReachableNodesResultType,
    data=ReachableNodesInput(required=True),
    description="Find all nodes of specified kinds reachable from a source node",
    resolver=reachable_nodes_resolver,
    required=True,
)
