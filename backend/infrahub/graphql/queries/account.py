from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import InternalAccountToken
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext
    from infrahub.permissions.constants import AssignedPermissions


class AccountTokenNode(ObjectType):
    id = Field(String, required=True)
    name = Field(String, required=False)
    expiration = Field(String, required=False)


class AccountTokenEdge(ObjectType):
    node = Field(AccountTokenNode, required=True)


class AccountTokenEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=AccountTokenEdge, required=True), required=True)


async def resolve_account_tokens(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    context: GraphqlContext = info.context

    if not context.account_session:
        raise ValueError("An account_session is mandatory to execute this query")

    if not context.account_session.authenticated_by_jwt:
        raise PermissionDeniedError("This operation requires authentication with a JWT token")

    fields = await extract_fields_first_node(info)

    filters = {"account__ids": [context.account_session.account_id]}
    response: dict[str, Any] = {}
    if "count" in fields:
        response["count"] = await NodeManager.count(db=context.db, schema=InternalAccountToken, filters=filters)
    if "edges" in fields:
        objs = await NodeManager.query(
            db=context.db, schema=InternalAccountToken, filters=filters, limit=limit, offset=offset
        )
        response["edges"] = [
            {"node": {"id": obj.id, "name": obj.name.value, "expiration": obj.expiration.value}} for obj in objs
        ]

    return response


AccountToken = Field(
    AccountTokenEdges, resolver=resolve_account_tokens, limit=Int(required=False), offset=Int(required=False)
)


class AccountGlobalPermissionNode(ObjectType):
    id = Field(String, required=True)
    name = Field(String, required=True)
    action = Field(String, required=True)
    identifier = Field(String, required=True)


class AccountObjectPermissionNode(ObjectType):
    id = Field(String, required=True)
    branch = Field(String, required=True)
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
    edges = Field(List(of_type=AccountGlobalPermissionEdge, required=True), required=True)


class AccountObjectPermissionEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=AccountObjectPermissionEdge, required=True), required=True)


class AccountPermissionsEdges(ObjectType):
    global_permissions = Field(AccountGlobalPermissionEdges, required=False)
    object_permissions = Field(AccountObjectPermissionEdges, required=False)


async def resolve_account_permissions(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
) -> dict:
    context: GraphqlContext = info.context

    if not context.account_session:
        raise ValueError("An account_session is mandatory to execute this query")

    fields = await extract_fields_first_node(info)
    permissions: AssignedPermissions = {"global_permissions": [], "object_permissions": []}
    for permission_backend in registry.permission_backends:
        backend_permissions = await permission_backend.load_permissions(
            db=context.db, account_id=context.account_session.account_id, branch=context.branch
        )
        permissions["global_permissions"].extend(backend_permissions["global_permissions"])
        permissions["object_permissions"].extend(backend_permissions["object_permissions"])

    response: dict[str, dict[str, Any]] = {}
    if "global_permissions" in fields:
        global_list = permissions["global_permissions"]
        response["global_permissions"] = {"count": len(global_list)}
        response["global_permissions"]["edges"] = [
            {"node": {"id": obj.id, "name": obj.name, "action": obj.action, "identifier": str(obj)}}
            for obj in global_list
        ]
    if "object_permissions" in fields:
        object_list = permissions["object_permissions"]
        response["object_permissions"] = {"count": len(object_list)}
        response["object_permissions"]["edges"] = [
            {
                "node": {
                    "id": obj.id,
                    "branch": obj.branch,
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


AccountPermissions = Field(AccountPermissionsEdges, resolver=resolve_account_permissions)
