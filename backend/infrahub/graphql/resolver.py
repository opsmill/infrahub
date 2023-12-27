from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from infrahub.core.manager import NodeManager

from .types import RELATIONS_PROPERTY_MAP, RELATIONS_PROPERTY_MAP_REVERSED
from .utils import extract_fields

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase


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
    at = info.context.get("infrahub_at")
    branch: Branch = info.context.get("infrahub_branch")
    db: InfrahubDatabase = info.context.get("infrahub_database")

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

    async with db.start_session() as db:
        objs = await NodeManager.query_peers(
            db=db,
            id=parent["id"],
            schema=node_rel,
            filters=filters,
            fields=fields,
            at=at,
            branch=branch,
        )

        if node_rel.cardinality == "many":
            return [await obj.to_graphql(db=db, fields=fields) for obj in objs]

        # If cardinality is one
        if not objs:
            return None

        return await objs[0].to_graphql(db=db, fields=fields)


async def single_relationship_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> Dict[str, Any]:
    """Resolver for relationships of cardinality=one for Edged responses

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema

    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch: Branch = info.context.get("infrahub_branch")
    db: InfrahubDatabase = info.context.get("infrahub_database")

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

    async with db.start_session() as db:
        objs = await NodeManager.query_peers(
            db=db,
            id=parent["id"],
            schema=node_rel,
            filters=filters,
            fields=node_fields,
            at=at,
            branch=branch,
        )

        if not objs:
            return response

        node_graph = await objs[0].to_graphql(db=db, fields=node_fields)
        for key, mapped in RELATIONS_PROPERTY_MAP_REVERSED.items():
            value = node_graph.pop(key, None)
            if value:
                response["properties"][mapped] = value
        response["node"] = node_graph
        return response


async def many_relationship_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> Dict[str, Any]:
    """Resolver for relationships of cardinality=many for Edged responses

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch: Branch = info.context.get("infrahub_branch")
    db: InfrahubDatabase = info.context.get("infrahub_database")

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

    async with db.start_session() as db:
        if "count" in fields:
            response["count"] = await NodeManager.count_peers(
                db=db,
                id=parent["id"],
                schema=node_rel,
                filters=filters,
                at=at,
                branch=branch,
            )
        objs = await NodeManager.query_peers(
            db=db,
            id=parent["id"],
            schema=node_rel,
            filters=filters,
            fields=node_fields,
            offset=offset,
            limit=limit,
            at=at,
            branch=branch,
        )

        if not objs:
            return response
        node_graph = [await obj.to_graphql(db=db, fields=node_fields) for obj in objs]

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
