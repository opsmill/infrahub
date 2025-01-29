from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import InternalAccountToken
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class AccountTokenNode(ObjectType):
    id = Field(String, required=True)
    name = Field(String, required=False)
    expiration = Field(String, required=False)


class AccountTokenEdge(ObjectType):
    node = Field(AccountTokenNode, required=True)


class AccountTokenEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=NonNull(AccountTokenEdge), required=True), required=True)


async def resolve_account_tokens(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    graphql_context: GraphqlContext = info.context

    if not graphql_context.account_session:
        raise ValueError("An account_session is mandatory to execute this query")

    if not graphql_context.account_session.authenticated_by_jwt:
        raise PermissionDeniedError("This operation requires authentication with a JWT token")

    fields = await extract_fields_first_node(info)

    filters = {"account__ids": [graphql_context.account_session.account_id]}
    response: dict[str, Any] = {}
    if "count" in fields:
        response["count"] = await NodeManager.count(db=graphql_context.db, schema=InternalAccountToken, filters=filters)
    if "edges" in fields:
        objs = await NodeManager.query(
            db=graphql_context.db, schema=InternalAccountToken, filters=filters, limit=limit, offset=offset
        )
        response["edges"] = [
            {"node": {"id": obj.id, "name": obj.name.value, "expiration": obj.expiration.value}} for obj in objs
        ]

    return response


AccountToken = Field(
    AccountTokenEdges,
    limit=Int(required=False),
    offset=Int(required=False),
    resolver=resolve_account_tokens,
    required=True,
)


class AccountGlobalPermissionNode(ObjectType):
    id = Field(String, required=True)
    description = Field(String, required=False)
    name = Field(String, required=True)
    action = Field(String, required=True)
    decision = Field(String, required=True)
    identifier = Field(String, required=True)


class AccountObjectPermissionNode(ObjectType):
    id = Field(String, required=True)
    description = Field(String, required=False)
    namespace = Field(String, required=True)
    name = Field(String, required=True)
    action = Field(String, required=True)
    decision = Field(String, required=True)
    identifier = Field(String, required=True)


class AccountGlobalPermissionEdge(ObjectType):
    node = Field(AccountGlobalPermissionNode, required=True)


class AccountObjectPermissionEdge(ObjectType):
    node = Field(AccountObjectPermissionNode, required=True)


class AccountGlobalPermissionEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=NonNull(AccountGlobalPermissionEdge), required=True), required=True)


class AccountObjectPermissionEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=NonNull(AccountObjectPermissionEdge), required=True), required=True)


class AccountPermissionsEdges(ObjectType):
    global_permissions = Field(AccountGlobalPermissionEdges, required=False)
    object_permissions = Field(AccountObjectPermissionEdges, required=False)


async def resolve_account_permissions(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
) -> dict:
    graphql_context: GraphqlContext = info.context

    if not graphql_context.account_session:
        raise ValueError("An account_session is mandatory to execute this query")

    fields = await extract_fields_first_node(info)

    response: dict[str, dict[str, Any]] = {}
    if "global_permissions" in fields:
        global_list = graphql_context.active_permissions.permissions["global_permissions"]
        response["global_permissions"] = {"count": len(global_list)}
        response["global_permissions"]["edges"] = [
            {
                "node": {
                    "id": obj.id,
                    "description": obj.description,
                    "action": obj.action,
                    "decision": obj.decision,
                    "identifier": str(obj),
                }
            }
            for obj in global_list
        ]
    if "object_permissions" in fields:
        object_list = graphql_context.active_permissions.permissions["object_permissions"]
        response["object_permissions"] = {"count": len(object_list)}
        response["object_permissions"]["edges"] = [
            {
                "node": {
                    "id": obj.id,
                    "description": obj.description,
                    "namespace": obj.namespace,
                    "name": obj.name,
                    "action": obj.action,
                    "decision": obj.decision,
                    "identifier": str(obj),
                }
            }
            for obj in object_list
        ]
    return response


AccountPermissions = Field(AccountPermissionsEdges, resolver=resolve_account_permissions, required=True)
