from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.manager import NodeManager
from infrahub.core.query.virtual_relationship import (
    VirtualRelationshipCountQuery,
    VirtualRelationshipGetPeersQuery,
)
from infrahub.graphql.field_extractor import extract_graphql_fields

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.relationship_schema import RelationshipSchema
    from infrahub.core.schema.virtual_relationship_schema import VirtualRelationshipSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


def _build_filters(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Build a filter dict from GraphQL kwargs, keeping only attribute filters."""
    return {key: value for key, value in kwargs.items() if "__" in key and value is not None}


async def _get_traversal_peer_ids(
    db: InfrahubDatabase,
    source_id: str,
    vr_schema: VirtualRelationshipSchema,
    relationship_schemas: list[RelationshipSchema],
    branch: Branch,
    at: Timestamp | None,
) -> list[str]:
    """Execute multi-hop traversal and return all reachable target node IDs."""
    async with db.start_session(read_only=True) as dbs:
        peers_query = await VirtualRelationshipGetPeersQuery.init(
            db=dbs,
            source_id=source_id,
            virtual_relationship=vr_schema,
            relationship_schemas=relationship_schemas,
            branch=branch,
            at=at,
        )
        await peers_query.execute(db=dbs)
    return peers_query.get_peer_ids()


async def _get_traversal_count(
    db: InfrahubDatabase,
    source_id: str,
    vr_schema: VirtualRelationshipSchema,
    relationship_schemas: list[RelationshipSchema],
    branch: Branch,
    at: Timestamp | None,
) -> int:
    """Execute multi-hop traversal count query."""
    async with db.start_session(read_only=True) as dbs:
        count_query = await VirtualRelationshipCountQuery.init(
            db=dbs,
            source_id=source_id,
            virtual_relationship=vr_schema,
            relationship_schemas=relationship_schemas,
            branch=branch,
            at=at,
        )
        await count_query.execute(db=dbs)
    return count_query.results[0].get("count") if count_query.results else 0


async def _fetch_nodes_filtered(
    db: InfrahubDatabase,
    peer_ids: list[str],
    vr_schema: VirtualRelationshipSchema,
    filters: dict[str, Any],
    branch: Branch,
    at: Timestamp | None,
    limit: int | None,
    offset: int | None,
) -> tuple[list[Node], int]:
    """Fetch target nodes with attribute filters applied. Returns (nodes, filtered_count)."""
    peer_schema = vr_schema.get_peer_schema(db=db, branch=branch)
    query_filters = {**filters, "ids": peer_ids}

    async with db.start_session(read_only=True) as dbs:
        nodes_list = await NodeManager.query(
            db=dbs,
            schema=peer_schema,
            filters=query_filters,
            branch=branch,
            at=at,
            limit=limit,
            offset=offset,
        )

    # Get filtered count (without pagination)
    if limit is not None or offset is not None:
        async with db.start_session(read_only=True) as dbs:
            all_filtered = await NodeManager.query(
                db=dbs,
                schema=peer_schema,
                filters=query_filters,
                branch=branch,
                at=at,
            )
        filtered_count = len(all_filtered)
    else:
        filtered_count = len(nodes_list)

    return nodes_list, filtered_count


async def _fetch_nodes_by_ids(
    db: InfrahubDatabase,
    peer_ids: list[str],
    branch: Branch,
    at: Timestamp | None,
    limit: int | None,
    offset: int | None,
) -> tuple[dict[str, Node], list[str]]:
    """Fetch target nodes by ID with pagination. Returns (nodes_map, ordered_ids)."""
    start = offset or 0
    end = start + limit if limit else None
    paginated_ids = peer_ids[start:end]

    async with db.start_session(read_only=True) as dbs:
        nodes_map = await NodeManager.get_many(
            db=dbs,
            ids=paginated_ids,
            branch=branch,
            at=at,
        )
    return nodes_map, paginated_ids


async def virtual_relationship_resolver(
    parent: dict,
    info: GraphQLResolveInfo,
    offset: int | None = None,
    limit: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Resolver for virtual relationships.

    Executes a multi-hop Cypher traversal query to collect target nodes,
    then fetches those nodes (with optional attribute filtering) and returns
    them in the standard NestedPaginated format.
    """
    graphql_context: GraphqlContext = info.context  # type: ignore[assignment]
    node_schema = info.parent_type.graphene_type._meta.schema  # type: ignore[attr-defined]

    fields = extract_graphql_fields(info=info)
    edges = fields.get("edges", {})
    node_fields = edges.get("node", {})

    vr_name = info.field_name
    vr_schema = node_schema.get_virtual_relationship(name=vr_name)
    source_id = parent["id"]
    response: dict[str, Any] = {"edges": [], "count": None}

    db = graphql_context.db
    branch = graphql_context.branch
    at = graphql_context.at

    relationship_schemas = _resolve_path_relationship_schemas(db=db, node_schema=node_schema, vr_schema=vr_schema)
    filters = _build_filters(kwargs)
    peer_ids = await _get_traversal_peer_ids(
        db=db,
        source_id=source_id,
        vr_schema=vr_schema,
        relationship_schemas=relationship_schemas,
        branch=branch,
        at=at,
    )

    if not peer_ids:
        response["count"] = 0 if "count" in fields else None
        return response

    if filters:
        nodes_list, filtered_count = await _fetch_nodes_filtered(
            db=db,
            peer_ids=peer_ids,
            vr_schema=vr_schema,
            filters=filters,
            branch=branch,
            at=at,
            limit=limit,
            offset=offset,
        )
        if "count" in fields:
            response["count"] = filtered_count
        nodes_map = {node.id: node for node in nodes_list}
        ordered_ids = [node.id for node in nodes_list]
    else:
        if "count" in fields:
            response["count"] = await _get_traversal_count(
                db=db,
                source_id=source_id,
                vr_schema=vr_schema,
                relationship_schemas=relationship_schemas,
                branch=branch,
                at=at,
            )
        if not node_fields:
            return response
        nodes_map, ordered_ids = await _fetch_nodes_by_ids(
            db=db,
            peer_ids=peer_ids,
            branch=branch,
            at=at,
            limit=limit,
            offset=offset,
        )

    entries = []
    async with db.start_session(read_only=True) as dbs:
        for node_id in ordered_ids:
            node = nodes_map.get(node_id)
            if not node:
                continue
            node_data = await node.to_graphql(
                db=dbs,
                fields=node_fields,
                related_node_ids=graphql_context.related_node_ids,
            )
            entry: dict[str, Any] = {"node": node_data}
            if edges.get("node_metadata"):
                entry["node_metadata"] = await node._build_meta_response("node_metadata", edges)
            entries.append(entry)

    response["edges"] = entries
    return response


def _find_relationship_across_implementations(
    db: Any,
    schema: Any,
    relationship_name: str,
) -> RelationshipSchema | None:
    """Find a relationship on a schema, checking concrete implementations for generics."""
    from infrahub.core.schema.generic_schema import GenericSchema

    rel = schema.get_relationship_or_none(name=relationship_name)
    if rel:
        return rel

    if isinstance(schema, GenericSchema) and hasattr(schema, "used_by"):
        for concrete_kind in schema.used_by or []:
            concrete_schema = db.schema.get(name=concrete_kind, branch=None, duplicate=False)
            rel = concrete_schema.get_relationship_or_none(name=relationship_name)
            if rel:
                return rel

    return None


def _resolve_path_relationship_schemas(
    db: Any,
    node_schema: Any,
    vr_schema: Any,
) -> list[RelationshipSchema]:
    """Walk the virtual relationship path and collect the RelationshipSchema for each segment."""
    segments = vr_schema.get_path_segments()
    schemas: list[RelationshipSchema] = []
    current_schema = node_schema

    for segment in segments:
        rel = _find_relationship_across_implementations(db=db, schema=current_schema, relationship_name=segment)
        if not rel:
            raise ValueError(f"Virtual relationship path segment '{segment}' not found on '{current_schema.kind}'")
        schemas.append(rel)
        current_schema = db.schema.get(name=rel.peer, branch=None, duplicate=False)

    return schemas
