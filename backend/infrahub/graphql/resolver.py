from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import infrahub.config as config
from infrahub.core.group import GroupAssociationType
from infrahub.core.manager import NodeManager
from infrahub.core.query.group import GroupGetAssociationQuery, NodeGetGroupListQuery
from infrahub_client.utils import deep_merge_dict

from .types import RELATIONS_PROPERTY_MAP, RELATIONS_PROPERTY_MAP_REVERSED
from .utils import extract_fields

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.schema import NodeSchema


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
    branch = info.context.get("infrahub_branch")
    # account = info.context.get("infrahub_account", None)
    db = info.context.get("infrahub_database")

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    filters = {
        f"{info.field_name}__{key}": value for key, value in kwargs.items() if "__" in key and value or key == "id"
    }

    async with db.session(database=config.SETTINGS.database.database) as new_session:
        objs = await NodeManager.query_peers(
            session=new_session,
            id=parent["id"],
            schema=node_rel,
            filters=filters,
            fields=fields,
            at=at,
            branch=branch,
        )

        if node_rel.cardinality == "many":
            return [await obj.to_graphql(session=new_session, fields=fields) for obj in objs]

        # If cardinality is one
        if not objs:
            return None

        return await objs[0].to_graphql(session=new_session, fields=fields)


async def relationship_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> Optional[Union[Dict, List]]:
    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch = info.context.get("infrahub_branch")
    db = info.context.get("infrahub_database")

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)

    # Extract the schema of the node on the other end of the relationship from the GQL Schema
    node_rel = node_schema.get_relationship(info.field_name)

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    filters = {
        f"{info.field_name}__{key}": value for key, value in kwargs.items() if "__" in key and value or key == "id"
    }

    async with db.session(database=config.SETTINGS.database.database) as new_session:
        objs = await NodeManager.query_peers(
            session=new_session,
            id=parent["id"],
            schema=node_rel,
            filters=filters,
            fields=fields,
            at=at,
            branch=branch,
        )

        if node_rel.cardinality == "many":
            return [await obj.to_graphql(session=new_session, fields=fields) for obj in objs]

        # If cardinality is one
        if not objs:
            return None

        return await objs[0].to_graphql(session=new_session, fields=fields)


async def single_relationship_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> Dict[str, Any]:
    """Resolver for relationships of cardinality=one for Edged responses

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema

    node_schema: NodeSchema = info.parent_type.graphene_type._meta.schema

    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch = info.context.get("infrahub_branch")
    db = info.context.get("infrahub_database")

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
        f"{info.field_name}__{key}": value for key, value in kwargs.items() if "__" in key and value or key == "id"
    }
    response: Dict[str, Any] = {"node": None, "properties": {}}
    async with db.session(database=config.SETTINGS.database.database) as new_session:
        objs = await NodeManager.query_peers(
            session=new_session,
            id=parent["id"],
            schema=node_rel,
            filters=filters,
            fields=node_fields,
            at=at,
            branch=branch,
        )

        if not objs:
            return response

        node_graph = await objs[0].to_graphql(session=new_session, fields=node_fields)
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
    branch = info.context.get("infrahub_branch")
    db = info.context.get("infrahub_database")

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
        f"{info.field_name}__{key}": value for key, value in kwargs.items() if "__" in key and value or key == "id"
    }

    response: Dict[str, Any] = {"edges": [], "count": None}
    async with db.session(database=config.SETTINGS.database.database) as new_session:
        if "count" in fields:
            response["count"] = await NodeManager.count_peers(
                session=new_session,
                id=parent["id"],
                schema=node_rel,
                filters=filters,
                at=at,
                branch=branch,
            )
        objs = await NodeManager.query_peers(
            session=new_session,
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
        node_graph = [await obj.to_graphql(session=new_session, fields=node_fields) for obj in objs]

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


async def node_groups_resolver(
    parent: dict, info: GraphQLResolveInfo, **kwargs  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    fields = await extract_fields(info.field_nodes[0].selection_set)

    response: Dict[str, Any] = {}

    node_id = parent.get("node", {}).get("id", None)
    if not node_id:
        raise ValueError("Unable to extract the node_id")

    if "member" in fields:
        response["member"] = await query_node_groups(
            node_id=node_id, fields=fields.get("member"), info=info, association_type=GroupAssociationType.MEMBER
        )

    elif "subscriber" in fields:
        response["subscriber"] = await query_node_groups(
            node_id=node_id,
            fields=fields.get("subscriber"),
            info=info,
            association_type=GroupAssociationType.SUBSCRIBER,
        )

    return response


async def query_node_groups(
    node_id: str,
    fields: dict,
    info: GraphQLResolveInfo,
    association_type: GroupAssociationType,
    offset: Optional[int] = None,  # pylint: disable=unused-argument
    limit: Optional[int] = None,  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch = info.context.get("infrahub_branch")
    db = info.context.get("infrahub_database")

    # Extract the name of the fields in the GQL query
    edges = fields.get("edges", {})
    node_fields = edges.get("node", {})

    response: Dict[str, Any] = {"edges": [], "count": None}
    async with db.session(database=config.SETTINGS.database.database) as new_session:
        query = await NodeGetGroupListQuery.init(
            session=new_session,
            association_type=association_type,
            ids=[node_id],
            branch=branch,
            at=at,
        )

        if "count" in fields:
            response["count"] = await query.count(session=new_session)

        await query.execute(session=new_session)
        groups_per_node = await query.get_groups_per_node()
        groups = groups_per_node.get(node_id, {})

        # if display_label has been requested we need to ensure we are querying the right fields
        if node_fields and "display_label" in node_fields:
            for schema in set(groups.values()):
                if schema.display_labels:
                    display_label_fields = schema.generate_fields_for_display_label()
                    node_fields = deep_merge_dict(node_fields, display_label_fields)

        objs = await NodeManager.get_many(
            session=new_session,
            ids=list(groups.keys()),
            fields=node_fields,
            include_owner=True,
            include_source=True,
            at=at,
            branch=branch,
        )
        if not objs:
            return response
        node_graph = [await obj.to_graphql(session=new_session, fields=node_fields) for obj in objs.values()]
        response["edges"] = [{"node": node} for node in node_graph]

        return response


async def default_paginated_group_association_resolver(
    parent: dict, info: GraphQLResolveInfo, **kwargs
) -> Dict[str, Any]:
    """Resolver for Group Associations for Edged responses

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the contextual information from the request context
    at = info.context.get("infrahub_at")
    branch = info.context.get("infrahub_branch")
    db = info.context.get("infrahub_database")

    # Extract the name of the fields in the GQL query
    fields = await extract_fields(info.field_nodes[0].selection_set)

    # Extract the type of Group Association that we need to use
    if info.field_name == "members":
        association_type = GroupAssociationType.MEMBER
    elif info.field_name == "subscribers":
        association_type = GroupAssociationType.SUBSCRIBER
    else:
        raise ValueError("Only values supported for info.field_name are 'members' and 'subscribers'")

    edges = fields.get("edges", {})
    node_fields = edges.get("node", {})

    # Extract only the filters from the kwargs and prepend the name of the field to the filters
    kwargs.pop("offset", None)
    kwargs.pop("limit", None)

    response: Dict[str, Any] = {"edges": [], "count": None}
    async with db.session(database=config.SETTINGS.database.database) as new_session:
        query = await GroupGetAssociationQuery.init(
            session=new_session,
            association_type=association_type,
            group_id=parent["id"],
            at=at,
            branch=branch,
        )
        if "count" in fields:
            response["count"] = await query.count(session=new_session)

        await query.execute(session=new_session)
        results = await query.get_members()

        # if display_label has been requested we need to ensure we are querying the right fields
        if node_fields and "display_label" in node_fields:
            for schema in set(results.values()):
                if schema.display_labels:
                    display_label_fields = schema.generate_fields_for_display_label()
                    node_fields = deep_merge_dict(node_fields, display_label_fields)

        objs = await NodeManager.get_many(
            session=new_session,
            ids=list(results.keys()),
            fields=node_fields,
            include_owner=True,
            include_source=True,
            at=at,
            branch=branch,
        )

        if not objs:
            return response
        node_graph = [await obj.to_graphql(session=new_session, fields=node_fields) for obj in objs.values()]

        response["edges"] = [{"node": node} for node in node_graph]
        return response
