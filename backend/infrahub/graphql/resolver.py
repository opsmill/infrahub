from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

import infrahub.config as config
from infrahub.core.group import GroupAssociationType
from infrahub.core.manager import NodeManager
from infrahub.core.query.group import GroupGetAssociationQuery, NodeGetGroupListQuery
from infrahub_client.utils import deep_merge_dict

from .utils import extract_fields

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


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
