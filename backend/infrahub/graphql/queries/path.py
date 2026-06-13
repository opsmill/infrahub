from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from graphene import Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphql import GraphQLError

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.exceptions import SchemaNotFoundError
from infrahub.graph_traversal._cypher import PathTraversalCypherRenderer
from infrahub.graph_traversal.executor import PathTraversalExecutor
from infrahub.graph_traversal.planning.models import TerminalById, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.graph_traversal.results import PathData
    from infrahub.graphql.initialization import GraphqlContext


MAX_PATHS = 100


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
    excluded_kinds = Field(
        List(of_type=NonNull(String)),
        required=True,
        description=(
            "Concrete node kinds excluded from this traversal: the default exclusions "
            "plus the requested excluded_kinds, minus included_kinds."
        ),
    )


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
        description=(
            "Additional namespaces to exclude from traversal. Unioned with the default "
            "excluded set (Core, Internal, Builtin, Lineage, Profile, Template); the "
            "defaults cannot be opted out of from this input."
        ),
    )
    excluded_kinds = List(
        of_type=NonNull(String),
        required=False,
        description=(
            "Specific node kinds to exclude from traversal paths. Unioned with the "
            "default excluded kinds (BuiltinIPNamespace and all kinds inheriting it); "
            "the defaults can be re-included via included_kinds."
        ),
    )
    included_kinds = List(
        of_type=NonNull(String),
        required=False,
        description=(
            "Kinds excluded by default (BuiltinIPNamespace and all kinds inheriting it) "
            "to re-include in traversal paths. Passing the generic re-includes every "
            "implementer. Has no effect on kinds passed in excluded_kinds in the same request."
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
    start_node_payload = _node_payload(
        node_id=path_data.start_node.uuid, kind=path_data.start_node.kind, labels_map=labels_map
    )
    hops: list[dict[str, Any]] = [{"node": start_node_payload, "relationship": None}]
    previous_kind = path_data.start_node.kind
    for hop in path_data.hops:
        node_payload = _node_payload(node_id=hop.node.uuid, kind=hop.node.kind, labels_map=labels_map)
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

    if max_paths > MAX_PATHS:
        raise GraphQLError(f"max_paths must be <= {MAX_PATHS}, got {max_paths}")

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

    user_filters = UserFilters.from_graphql_input(data)
    try:
        planner = SchemaPlanner(
            schema_branch=graphql_context.db.schema.get_schema_branch(name=graphql_context.branch.name),
            branch=graphql_context.branch,
            permission_resolver=graphql_context.active_permissions.resolver,
        )
        plan = planner.plan(
            source_kind=source_node.get_kind(),
            terminal_predicate=TerminalById(node_id=destination_id, kind=destination_node.get_kind()),
            max_depth=int(max_depth),
            user_filters=user_filters,
        )
    except ValueError as exc:
        raise GraphQLError(str(exc)) from exc

    if plan.is_empty:
        # No schema route survives planning, return an empty result
        path_data_list: list[PathData] = []
    else:
        executor = PathTraversalExecutor(
            db=graphql_context.db,
            branch=graphql_context.branch,
            renderer=PathTraversalCypherRenderer(
                branch=graphql_context.branch,
                default_branch_name=registry.default_branch,
            ),
        )
        try:
            path_data_list = await executor.run(
                plan=plan,
                source_id=source_id,
                max_paths=max_paths,
                at=graphql_context.at,
            )
        except ValueError as exc:
            raise GraphQLError(str(exc)) from exc

    all_node_ids: set[str] = {source_id, destination_id}
    for path_data in path_data_list:
        all_node_ids.add(path_data.start_node.uuid)
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
        "excluded_kinds": sorted(plan.excluded_kinds),
    }


InfrahubPathTraversal = Field(
    PathTraversalResultType,
    data=PathTraversalInput(required=True),
    description="Find all shortest paths between two nodes in the graph",
    resolver=path_traversal_resolver,
    required=True,
)
