from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from infrahub_sdk.utils import extract_fields

from infrahub.core.constants import RelationshipHierarchyDirection
from infrahub.core.manager import NodeManager
from infrahub.core.query.node import NodeGetHierarchyQuery

from .types import RELATIONS_PROPERTY_MAP, RELATIONS_PROPERTY_MAP_REVERSED

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.schema import NodeSchema
    from infrahub.graphql import GraphqlContext


async def default_resolver(*args, **kwargs):
    """Not sure why but the default resolver returns sometime 4 positional args and sometime 2.

    When it returns 4, they are organized as follow
        - field name
        - ???
        - parent
        - info
    When it returns 2, they are organized as follow
        - parent
        - info
    """

    parent = None
    info = None
    field_name = None

    if len(args) == 4:
        parent = args[2]
        info = args[3]
        field_name = args[0]
    elif len(args) == 2:
        parent = args[0]
        info = args[1]
        field_name = info.field_name
    else:
        raise ValueError(f"expected either 2 or 4 args for default_resolver, got {len(args)}")

    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    # If the field is an attribute, return its value directly
    if field_name not in node_schema.relationship_names:
        return parent.get(field_name, None)

    # Extract the contextual information from the request context
    context: GraphqlContext = info.context

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    filters = {
        f"{info.field_name}__{key}": value
        for key, value in kwargs.items()
        if "__" in key and value or key in ["id", "ids"]
    }

    async with context.db.start_session() as db:
        objs = await NodeManager.query_peers(
            db=db,
            ids=[parent["id"]],
            source_kind=node_schema.kind,
            schema=node_rel,
            filters=filters,
            fields=fields,
            at=context.at,
            branch=context.branch,
        )

        if node_rel.cardinality == "many":
            return [
                await obj.to_graphql(db=db, fields=fields, related_node_ids=context.related_node_ids) for obj in objs
            ]

        # If cardinality is one
        if not objs:
            return None

        return await objs[0].to_graphql(db=db, fields=fields, related_node_ids=context.related_node_ids)


async def single_relationship_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> Dict[str, Any]:
    """Resolver for relationships of cardinality=one for Edged responses

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema

    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    context: GraphqlContext = info.context

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)
    node_fields = fields.get("node", {})
    property_fields = fields.get("properties", {})
    for key, value in property_fields.items():
        mapped_name = RELATIONS_PROPERTY_MAP[key]
        node_fields[mapped_name] = value

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)
    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    filters = {
        f"{info.field_name}__{key}": value
        for key, value in kwargs.items()
        if "__" in key and value or key in ["id", "ids"]
    }
    response: Dict[str, Any] = {"node": None, "properties": {}}

    async with context.db.start_session() as db:
        objs = await NodeManager.query_peers(
            db=db,
            ids=[parent["id"]],
            source_kind=node_schema.kind,
            schema=node_rel,
            filters=filters,
            fields=node_fields,
            at=context.at,
            branch=context.branch,
        )

        if not objs:
            return response

        node_graph = await objs[0].to_graphql(db=db, fields=node_fields, related_node_ids=context.related_node_ids)
        for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
            value = node_graph.pop(key, None)
            if value:
                response["properties"][mapped] = value
        response["node"] = node_graph
        return response


async def many_relationship_resolver(
    parent: dict, info: GraphQLResolveInfo, include_descendants: Optional[bool] = False, **kwargs
) -> Dict[str, Any]:
    """Resolver for relationships of cardinality=many for Edged responses

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    context: GraphqlContext = info.context

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)
    edges = fields.get("edges", {})
    node_fields = edges.get("node", {})
    property_fields = edges.get("properties", {})
    for key, value in property_fields.items():
        mapped_name = RELATIONS_PROPERTY_MAP[key]
        node_fields[mapped_name] = value

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    offset = kwargs.pop("offset", None)
    limit = kwargs.pop("limit", None)

    filters = {
        f"{info.field_name}__{key}": value
        for key, value in kwargs.items()
        if "__" in key and value or key in ["id", "ids"]
    }

    response: Dict[str, Any] = {"edges": [], "count": None}

    async with context.db.start_session() as db:
        ids = [parent["id"]]
        if include_descendants:
            query = await NodeGetHierarchyQuery.init(
                db=db,
                direction=RelationshipHierarchyDirection.DESCENDANTS,
                node_id=parent["id"],
                node_schema=node_schema,
                at=context.at,
                branch=context.branch,
            )
            await query.execute(db=db)
            descendants_ids = list(query.get_peer_ids())
            ids.extend(descendants_ids)

        if "count" in fields:
            response["count"] = await NodeManager.count_peers(
                db=db,
                ids=ids,
                source_kind=node_schema.kind,
                schema=node_rel,
                filters=filters,
                at=context.at,
                branch=context.branch,
            )

        if not node_fields:
            return response

        objs = await NodeManager.query_peers(
            db=db,
            ids=ids,
            source_kind=node_schema.kind,
            schema=node_rel,
            filters=filters,
            fields=node_fields,
            offset=offset,
            limit=limit,
            at=context.at,
            branch=context.branch,
        )

        if not objs:
            return response
        node_graph = [
            await obj.to_graphql(db=db, fields=node_fields, related_node_ids=context.related_node_ids) for obj in objs
        ]

        entries = []
        for node in node_graph:
            entry = {"node": {}, "properties": {}}
            for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
                value = node.pop(key, None)
                if value:
                    entry["properties"][mapped] = value
            entry["node"] = node
            entries.append(entry)
        response["edges"] = entries

        return response


async def ancestors_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> Dict[str, Any]:
    return await hierarchy_resolver(
        direction=RelationshipHierarchyDirection.ANCESTORS, parent=parent, info=info, **kwargs
    )


async def descendants_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> Dict[str, Any]:
    return await hierarchy_resolver(
        direction=RelationshipHierarchyDirection.DESCENDANTS, parent=parent, info=info, **kwargs
    )


async def hierarchy_resolver(
    direction: RelationshipHierarchyDirection, parent: dict, info: GraphQLResolveInfo, **kwargs
) -> Dict[str, Any]:
    """Resolver for ancestors and dependants for Hierarchical nodes

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    context: GraphqlContext = info.context

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)
    edges = fields.get("edges", {})
    node_fields = edges.get("node", {})

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    offset = kwargs.pop("offset", None)
    limit = kwargs.pop("limit", None)
    filters = {
        f"{info.field_name}__{key}": value
        for key, value in kwargs.items()
        if "__" in key and value or key in ["id", "ids"]
    }

    response: Dict[str, Any] = {"edges": [], "count": None}

    async with context.db.start_session() as db:
        if "count" in fields:
            response["count"] = await NodeManager.count_hierarchy(
                db=db,
                id=parent["id"],
                direction=direction,
                node_schema=node_schema,
                filters=filters,
                at=context.at,
                branch=context.branch,
            )

        if not node_fields:
            return response

        objs = await NodeManager.query_hierarchy(
            db=db,
            id=parent["id"],
            direction=direction,
            node_schema=node_schema,
            filters=filters,
            fields=node_fields,
            offset=offset,
            limit=limit,
            at=context.at,
            branch=context.branch,
        )

        if not objs:
            return response
        node_graph = [await obj.to_graphql(db=db, fields=node_fields) for obj in objs.values()]

        entries = []
        for node in node_graph:
            entry = {"node": {}, "properties": {}}
            entry["node"] = node
            entries.append(entry)
        response["edges"] = entries

        return response
