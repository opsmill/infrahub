from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from graphene import Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphql import GraphQLError

from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.manager import NodeManager
from infrahub.exceptions import SchemaNotFoundError
from infrahub.graph_traversal.path import PathTraversalQuery
from infrahub.graph_traversal.planning.constants import DEFAULT_EXCLUDED_NAMESPACES
from infrahub.graph_traversal.planning.models import TerminalById, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.permissions.resolver import PermissionResolver

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.graph_traversal.results import PathData
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

    user_filters = UserFilters(
        kind_filter=frozenset(kind_filter),
        excluded_kinds=frozenset(excluded_kinds),
        excluded_namespaces=frozenset(
            excluded_namespaces if excluded_namespaces is not None else DEFAULT_EXCLUDED_NAMESPACES
        ),
        relationship_filter=frozenset(relationship_filter),
    )
    try:
        planner = SchemaPlanner(
            schema_branch=graphql_context.db.schema.get_schema_branch(name=graphql_context.branch.name),
            branch=graphql_context.branch,
            permission_resolver=_wildcard_allow_resolver(),
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
        query = await PathTraversalQuery.init(
            db=graphql_context.db,
            branch=graphql_context.branch,
            at=graphql_context.at,
            plan=plan,
            source_id=source_id,
            default_branch_name=registry.default_branch,
            max_paths=max_paths,
        )
        await query.execute(db=graphql_context.db)
        path_data_list = query.get_paths()

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
    }


def _wildcard_allow_resolver() -> PermissionResolver:
    """Build a permissive ``PermissionResolver`` that allows view on any kind.

    Transitional: matches the pre-refactor query's "no permission check"
    behavior. Phase 3's resolver refactor replaces this with a real
    ``PermissionLoader.load(...)`` flow scoped to the requester's session.
    """
    return PermissionResolver(
        permissions={
            "global_permissions": [],
            "object_permissions": [
                ObjectPermission(
                    namespace="*",
                    name="*",
                    action="view",
                    decision=PermissionDecisionFlag.ALLOW_ALL.value,
                ),
            ],
        },
        default_branch_name=registry.default_branch,
    )


InfrahubPathTraversal = Field(
    PathTraversalResultType,
    data=PathTraversalInput(required=True),
    description="Find all shortest paths between two nodes in the graph",
    resolver=path_traversal_resolver,
    required=True,
)
