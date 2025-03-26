from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphql.type.definition import GraphQLNonNull
from infrahub_sdk.utils import extract_fields
from opentelemetry import trace

from infrahub.core.constants import BranchSupportType, InfrahubKind, RelationshipHierarchyDirection
from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFoundError

from ..models import OrderModel
from ..parser import extract_selection
from ..permissions import get_permissions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.schema import NodeSchema
    from infrahub.graphql.initialization import GraphqlContext


@trace.get_tracer(__name__).start_as_current_span("account_resolver")
async def account_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
) -> dict:
    fields = await extract_fields(info.field_nodes[0].selection_set)
    graphql_context: GraphqlContext = info.context

    async with graphql_context.db.start_session() as db:
        results = await NodeManager.query(
            schema=InfrahubKind.GENERICACCOUNT,
            filters={"ids": [graphql_context.account_session.account_id]},
            fields=fields,
            db=db,
            order=OrderModel(disable=True),
        )
        if results:
            account_profile = await results[0].to_graphql(db=db, fields=fields)
            return account_profile

        raise NodeNotFoundError(
            node_type=InfrahubKind.GENERICACCOUNT, identifier=graphql_context.account_session.account_id
        )


@trace.get_tracer(__name__).start_as_current_span("default_resolver")
async def default_resolver(*args: Any, **kwargs) -> dict | list[dict] | None:
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
    node_schema: NodeSchema = (
        info.parent_type.of_type.graphene_type._meta.schema
        if isinstance(info.parent_type, GraphQLNonNull)
        else info.parent_type.graphene_type._meta.schema
    )

    # If the field is an attribute, return its value directly
    if field_name not in node_schema.relationship_names:
        return parent.get(field_name, None)

    # Extract the contextual information from the request context
    graphql_context: GraphqlContext = info.context

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

    async with graphql_context.db.start_session() as db:
        objs = await NodeManager.query_peers(
            db=db,
            ids=[parent["id"]],
            source_kind=node_schema.kind,
            schema=node_rel,
            filters=filters,
            fields=fields,
            at=graphql_context.at,
            branch=graphql_context.branch,
            branch_agnostic=node_rel.branch is BranchSupportType.AGNOSTIC,
            fetch_peers=True,
        )

        if node_rel.cardinality == "many":
            return [
                await obj.to_graphql(db=db, fields=fields, related_node_ids=graphql_context.related_node_ids)
                for obj in objs
            ]

        # If cardinality is one
        if not objs:
            return None

        return await objs[0].to_graphql(db=db, fields=fields, related_node_ids=graphql_context.related_node_ids)


@trace.get_tracer(__name__).start_as_current_span("parent_field_name_resolver")
async def parent_field_name_resolver(parent: dict[str, dict], info: GraphQLResolveInfo) -> dict:
    """This resolver gets used when we know that the parent resolver has already gathered the required information.

    An example of this is the permissions field at the top level within default_paginated_list_resolver()
    """

    return parent[info.field_name]


@trace.get_tracer(__name__).start_as_current_span("default_paginated_list_resolver")
async def default_paginated_list_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    offset: int | None = None,
    limit: int | None = None,
    order: OrderModel | None = None,
    partial_match: bool = False,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    schema: NodeSchema = (
        info.return_type.of_type.graphene_type._meta.schema
        if isinstance(info.return_type, GraphQLNonNull)
        else info.return_type.graphene_type._meta.schema
    )

    fields = await extract_selection(info.field_nodes[0], schema=schema)

    graphql_context: GraphqlContext = info.context
    async with graphql_context.db.start_session() as db:
        response: dict[str, Any] = {"edges": []}
        filters = {
            key: value for key, value in kwargs.items() if ("__" in key and value is not None) or key in ("ids", "hfid")
        }

        edges = fields.get("edges", {})
        node_fields = edges.get("node", {})

        permission_set: dict[str, Any] | None = None
        permissions = (
            await get_permissions(schema=schema, graphql_context=graphql_context)
            if graphql_context.permissions
            else None
        )
        if fields.get("permissions"):
            response["permissions"] = permissions

        if permissions:
            for edge in permissions["edges"]:
                if edge["node"]["kind"] == schema.kind:
                    permission_set = edge["node"]

        objs = []
        if edges or "hfid" in filters:
            objs = await NodeManager.query(
                db=db,
                schema=schema,
                filters=filters or None,
                fields=node_fields,
                at=graphql_context.at,
                branch=graphql_context.branch,
                limit=limit,
                offset=offset,
                account=graphql_context.account_session,
                include_source=True,
                include_owner=True,
                partial_match=partial_match,
                order=order,
            )

        if "count" in fields:
            if filters.get("hfid"):
                response["count"] = len(objs)
            else:
                response["count"] = await NodeManager.count(
                    db=db,
                    schema=schema,
                    filters=filters,
                    at=graphql_context.at,
                    branch=graphql_context.branch,
                    partial_match=partial_match,
                )

        # get peer IDs for relationships
        if objs:
            objects = [
                {
                    "node": await obj.to_graphql(
                        db=db,
                        fields=node_fields,
                        related_node_ids=graphql_context.related_node_ids,
                        permissions=permission_set,
                    )
                }
                for obj in objs
            ]
            response["edges"] = objects

        return response


@trace.get_tracer(__name__).start_as_current_span("single_relationship_resolver")
async def single_relationship_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs: Any) -> dict[str, Any]:
    graphql_context: GraphqlContext = info.context
    resolver = graphql_context.single_relationship_resolver
    return await resolver.resolve(parent=parent, info=info, **kwargs)


@trace.get_tracer(__name__).start_as_current_span("many_relationship_resolver")
async def many_relationship_resolver(
    parent: dict, info: GraphQLResolveInfo, include_descendants: bool | None = False, **kwargs: Any
) -> dict[str, Any]:
    graphql_context: GraphqlContext = info.context
    resolver = graphql_context.many_relationship_resolver
    return await resolver.resolve(parent=parent, info=info, include_descendants=include_descendants, **kwargs)


async def ancestors_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> dict[str, Any]:
    return await hierarchy_resolver(
        direction=RelationshipHierarchyDirection.ANCESTORS, parent=parent, info=info, **kwargs
    )


async def descendants_resolver(parent: dict, info: GraphQLResolveInfo, **kwargs) -> dict[str, Any]:
    return await hierarchy_resolver(
        direction=RelationshipHierarchyDirection.DESCENDANTS, parent=parent, info=info, **kwargs
    )


@trace.get_tracer(__name__).start_as_current_span("hierarchy_resolver")
async def hierarchy_resolver(
    direction: RelationshipHierarchyDirection, parent: dict, info: GraphQLResolveInfo, **kwargs
) -> dict[str, Any]:
    """Resolver for ancestors and dependants for Hierarchical nodes

    This resolver is used for paginated responses and as such we redefined the requested
    fields by only reusing information below the 'node' key.
    """
    # Extract the InfraHub schema by inspecting the GQL Schema
    node_schema: NodeSchema = (
        info.parent_type.of_type.graphene_type._meta.schema
        if isinstance(info.parent_type, GraphQLNonNull)
        else info.parent_type.graphene_type._meta.schema
    )

    graphql_context: GraphqlContext = info.context

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

    response: dict[str, Any] = {"edges": [], "count": None}

    async with graphql_context.db.start_session() as db:
        if "count" in fields:
            response["count"] = await NodeManager.count_hierarchy(
                db=db,
                id=parent["id"],
                direction=direction,
                node_schema=node_schema,
                filters=filters,
                at=graphql_context.at,
                branch=graphql_context.branch,
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
            at=graphql_context.at,
            branch=graphql_context.branch,
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
