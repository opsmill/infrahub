from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphql import GraphQLError

from infrahub import config
from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import SchemaNotFoundError
from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
from infrahub.graph_traversal.executor import PathTraversalExecutor
from infrahub.graph_traversal.planning.models import TerminalById, UserFilters
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from infrahub.graph_traversal.runner import DefaultQueryRunner
from infrahub.log import get_logger

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes, RelationshipSchema
    from infrahub.graph_traversal.results import PathData
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger()


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
    truncated_at_depth = Field(
        Int,
        required=False,
        description=(
            "Null when the search completed. Otherwise the depth at which it ran out of budget: "
            "the returned paths are complete only for depths below this value, and deeper paths may exist."
        ),
    )


class PathTraversalInput(InputObjectType):
    source_id = String(required=True, description="UUID of the start node")
    destination_id = String(required=True, description="UUID of the end node")
    max_depth = Int(required=False, default_value=5, description="Maximum number of node hops (default: 5, max: 30)")
    max_paths = Int(
        required=False, default_value=10, description="Maximum number of paths to return (default: 10, max: 100)"
    )
    shortest_paths_only = Boolean(
        required=False,
        default_value=True,
        description=(
            "When true (default), return only the shortest path through each intermediate object — "
            "fast, but excludes longer paths through the same intermediate objects. When false, "
            "return all loopless paths up to max_paths."
        ),
    )
    kind_filter = List(
        of_type=NonNull(String), required=False, description="Filter to only traverse through nodes of these kinds"
    )
    relationship_filter = List(
        of_type=NonNull(String),
        required=False,
        description=(
            "Filter to only follow relationships with these identifiers (the relationship's schema "
            "identifier, e.g. `device__interface`), not relationship names (e.g. `interfaces`)."
        ),
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


def _get_schema_or_none(graphql_context: GraphqlContext, kind: str) -> MainSchemaTypes | None:
    try:
        return graphql_context.db.schema.get(name=kind, branch=graphql_context.branch, duplicate=False)
    except SchemaNotFoundError:
        return None


def _candidate_relationships(
    schema: MainSchemaTypes, identifier: str, other_kind: str, other_schema: MainSchemaTypes | None
) -> list[RelationshipSchema]:
    """Relationships declared under ``identifier``, narrowed to those whose peer covers the other endpoint."""
    candidates = schema.get_relationships_by_identifier(id=identifier)
    other_kinds = {other_kind}
    if isinstance(other_schema, NodeSchema):
        other_kinds.update(other_schema.inherit_from)
    matching = [candidate for candidate in candidates if candidate.peer in other_kinds]
    return matching or candidates


def select_hop_relationships(
    *,
    from_schema: MainSchemaTypes | None,
    to_schema: MainSchemaTypes | None,
    from_kind: str,
    to_kind: str,
    identifier: str,
) -> tuple[RelationshipSchema | None, RelationshipSchema | None]:
    """Pick the relationship each end of a hop holds for ``identifier``.

    Both ends of an edge share one identifier, like a hierarchy's ``parent`` and
    ``children``, so candidates are narrowed by peer kind and paired by mirrored
    direction. The pick is exact when one mirrored pair remains. When peers cover
    both ends, as when they default to the hierarchy generic, the schema cannot
    tell the ends apart: the first pair is kept, a deterministic guess.
    """
    from_candidates = (
        _candidate_relationships(schema=from_schema, identifier=identifier, other_kind=to_kind, other_schema=to_schema)
        if from_schema
        else []
    )
    to_candidates = (
        _candidate_relationships(
            schema=to_schema, identifier=identifier, other_kind=from_kind, other_schema=from_schema
        )
        if to_schema
        else []
    )

    pairs = [(from_rel, to_rel) for from_rel in from_candidates for to_rel in to_candidates if from_rel.mirrors(to_rel)]
    if not pairs:
        return (
            from_candidates[0] if from_candidates else None,
            to_candidates[0] if to_candidates else None,
        )
    if len(pairs) > 1:
        log.warning(
            "Several relationship pairs mirror each other for this hop, keeping the first one",
            from_kind=from_kind,
            to_kind=to_kind,
            identifier=identifier,
        )
    return pairs[0]


def _resolve_relationship(
    graphql_context: GraphqlContext, identifier: str, from_kind: str, to_kind: str
) -> dict[str, str]:
    """Project a hop's relationship identifier into bidirectional API fields.

    Falls back to the identifier when schema lookup fails (e.g. legacy data or
    unknown kinds).
    """
    from_rel, to_rel = select_hop_relationships(
        from_schema=_get_schema_or_none(graphql_context=graphql_context, kind=from_kind),
        to_schema=_get_schema_or_none(graphql_context=graphql_context, kind=to_kind),
        from_kind=from_kind,
        to_kind=to_kind,
        identifier=identifier,
    )

    kind = ""
    if from_rel is not None:
        kind = from_rel.kind.value
    elif to_rel is not None:
        kind = to_rel.kind.value

    return {
        "from_rel": from_rel.name if from_rel else identifier,
        "from_label": (from_rel.label or from_rel.name) if from_rel else identifier,
        "to_rel": to_rel.name if to_rel else identifier,
        "to_label": (to_rel.label or to_rel.name) if to_rel else identifier,
        "kind": kind,
    }


def _path_data_to_result(
    path_data: PathData,
    labels_map: dict[str, dict[str, Any]],
    graphql_context: GraphqlContext,
    relationship_cache: dict[tuple[str, str, str], dict[str, str]],
) -> dict[str, Any]:
    """Project one path into the API shape.

    ``relationship_cache`` is request-scoped: a hop triple always resolves to the same
    payload, and caching keeps the ambiguous-pair warning to one line per triple.
    """
    start_node_payload = _node_payload(
        node_id=path_data.start_node.uuid, kind=path_data.start_node.kind, labels_map=labels_map
    )
    hops: list[dict[str, Any]] = [{"node": start_node_payload, "relationship": None}]
    previous_kind = path_data.start_node.kind
    for hop in path_data.hops:
        node_payload = _node_payload(node_id=hop.node.uuid, kind=hop.node.kind, labels_map=labels_map)
        cache_key = (hop.relationship_identifier, previous_kind, hop.node.kind)
        relationship_payload = relationship_cache.get(cache_key)
        if relationship_payload is None:
            relationship_payload = _resolve_relationship(
                graphql_context=graphql_context,
                identifier=hop.relationship_identifier,
                from_kind=previous_kind,
                to_kind=hop.node.kind,
            )
            relationship_cache[cache_key] = relationship_payload
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
    shortest_paths_only = data.shortest_paths_only if data.shortest_paths_only is not None else True

    if not 1 <= max_paths <= MAX_PATHS:
        raise GraphQLError(f"max_paths must be in [1, {MAX_PATHS}], got {max_paths}")

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

    truncated_at_depth: int | None = None
    if plan.is_empty:
        # No schema route survives planning, return an empty result
        path_data_list: list[PathData] = []
    else:
        executor = PathTraversalExecutor(
            db=graphql_context.db,
            branch=graphql_context.branch,
            renderer=GraphTraversalCypherRenderer(
                branch=graphql_context.branch,
                default_branch_name=registry.default_branch,
            ),
            query_runner=DefaultQueryRunner(),
            timeout_seconds=config.SETTINGS.database.path_traversal_query_timeout,
        )
        try:
            result = await executor.run(
                plan=plan,
                source_id=source_id,
                max_paths=max_paths,
                shortest_paths_only=shortest_paths_only,
                at=graphql_context.at,
            )
            path_data_list = result.paths
            truncated_at_depth = result.truncated_at_depth
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

    relationship_cache: dict[tuple[str, str, str], dict[str, str]] = {}
    paths = [_path_data_to_result(p, labels_map, graphql_context, relationship_cache) for p in path_data_list]

    return {
        "paths": paths,
        "source": source_info,
        "destination": destination_info,
        "count": len(path_data_list),
        "excluded_kinds": sorted(plan.excluded_kinds),
        "truncated_at_depth": truncated_at_depth,
    }


InfrahubPathTraversal = Field(
    PathTraversalResultType,
    data=PathTraversalInput(required=True),
    description="Find all shortest paths between two nodes in the graph",
    resolver=path_traversal_resolver,
    required=True,
)
