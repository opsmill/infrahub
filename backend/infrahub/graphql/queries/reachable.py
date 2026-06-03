from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphql import GraphQLError

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.exceptions import SchemaNotFoundError
from infrahub.graph_traversal._cypher import PathTraversalCypherRenderer
from infrahub.graph_traversal.planning.models import TerminalByKinds, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from infrahub.graph_traversal.reachable import ReachableNodesQuery
from infrahub.graphql.queries.path import (
    PathNodeType,
    PathResultType,
    _get_node_labels,
    _node_payload,
    _path_data_to_result,
)

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node import Node
    from infrahub.graph_traversal.reachable import ReachableNodeData
    from infrahub.graphql.initialization import GraphqlContext


class ReachableNodeType(ObjectType):
    node = Field(PathNodeType, required=True, description="Reachable node")
    depth = Field(Int, required=True, description="Hops from source node")
    path = Field(PathResultType, required=True, description="Full path from source to this node")


class ReachableNodesResultType(ObjectType):
    source = Field(PathNodeType, required=True, description="The source node")
    dependencies = Field(
        List(of_type=NonNull(ReachableNodeType)),
        required=True,
        description="Reachable nodes of the requested kinds, one entry per (node, path) pair",
    )
    count = Field(Int, required=True, description="Number of dependency entries returned")


class ReachableNodesInput(InputObjectType):
    source_id = String(required=True, description="UUID of the source node")
    target_kinds = List(of_type=NonNull(String), required=True, description="Node kinds to search for")
    max_depth = Int(required=False, default_value=5, description="Maximum traversal depth (default: 5, max: 20)")
    max_results = Int(
        required=False,
        default_value=50,
        description="Maximum number of distinct terminal nodes to discover (default: 50, max: 200)",
    )
    max_paths = Int(
        required=False,
        default_value=500,
        description="Maximum total paths returned across all discovered terminals (default: 500, max: 5000)",
    )


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
    max_paths = 500 if data.max_paths is None else data.max_paths

    if not target_kinds:
        raise GraphQLError("At least one target kind is required")

    source_node: Node | None = await NodeManager.get_one(
        db=graphql_context.db,
        branch=graphql_context.branch,
        at=graphql_context.at,
        id=source_id,
    )
    if not source_node:
        raise GraphQLError(f"Source node not found: {source_id}")

    schema_branch = graphql_context.db.schema.get_schema_branch(name=graphql_context.branch.name)
    for kind in target_kinds:
        try:
            schema_branch.get(name=kind, duplicate=False)
        except SchemaNotFoundError as exc:
            raise GraphQLError(f"Unknown target kind: {kind}") from exc

    user_filters = UserFilters.from_graphql_input(data)
    try:
        planner = SchemaPlanner(
            schema_branch=schema_branch,
            branch=graphql_context.branch,
            permission_resolver=graphql_context.active_permissions.resolver,
        )
        plan = planner.plan(
            source_kind=source_node.get_kind(),
            terminal_predicate=TerminalByKinds(kinds=frozenset(target_kinds)),
            max_depth=int(max_depth),
            user_filters=user_filters,
        )
    except ValueError as exc:
        raise GraphQLError(str(exc)) from exc

    reachable_data: list[ReachableNodeData] = []
    if not plan.is_empty:
        renderer = PathTraversalCypherRenderer(
            branch=graphql_context.branch,
            default_branch_name=registry.default_branch,
        )
        try:
            query = await ReachableNodesQuery.init(
                db=graphql_context.db,
                branch=graphql_context.branch,
                at=graphql_context.at,
                renderer=renderer,
                plan=plan,
                source_id=source_id,
                max_targets=max_results,
                max_paths=max_paths,
            )
        except ValueError as exc:
            raise GraphQLError(str(exc)) from exc
        await query.execute(db=graphql_context.db)
        reachable_data = query.get_reachable_nodes()

    all_ids: set[str] = {source_id}
    for n in reachable_data:
        all_ids.add(n.node.uuid)
        all_ids.update(hop.node.uuid for hop in n.path.hops)

    labels_map = await _get_node_labels(graphql_context=graphql_context, node_ids=all_ids)

    source_info = _node_payload(node_id=source_node.id, kind=source_node.get_kind(), labels_map=labels_map)

    dependencies = [
        {
            "node": _node_payload(node_id=n.node.uuid, kind=n.node.kind, labels_map=labels_map),
            "depth": n.depth,
            "path": _path_data_to_result(n.path, labels_map, graphql_context),
        }
        for n in reachable_data
    ]

    return {
        "source": source_info,
        "dependencies": dependencies,
        "count": len(dependencies),
    }


InfrahubReachableNodes = Field(
    ReachableNodesResultType,
    data=ReachableNodesInput(required=True),
    description="Find all nodes of specified kinds reachable from a source node",
    resolver=reachable_nodes_resolver,
    required=True,
)
