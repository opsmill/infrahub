from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.protocols import InternalAccountToken
    from infrahub.graphql import GraphqlContext


class AccountTokenNode(ObjectType):
    id = Field(String, required=True)
    name = Field(String, required=False)
    expiration = Field(String, required=False)


class AccountTokenEdge(ObjectType):
    node = Field(AccountTokenNode, required=True)


class AccountTokenEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=AccountTokenEdge, required=True), required=False)


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

    node_schema = registry.get_node_schema(name=InfrahubKind.ACCOUNTTOKEN)
    fields = await extract_fields_first_node(info)

    filters = {"account__ids": [context.account_session.account_id]}
    response: dict[str, Any] = {}
    if "count" in fields:
        response["count"] = await NodeManager.count(db=context.db, schema=node_schema, filters=filters)
    if "edges" in fields:
        objs: List[InternalAccountToken] = await NodeManager.query(
            db=context.db, schema=node_schema, filters=filters, limit=limit, offset=offset
        )

        if objs:
            objects = [
                {"node": {"id": obj.id, "name": obj.name.value, "expiration": obj.expiration.value}} for obj in objs
            ]
            response["edges"] = objects

    return response


AccountToken = Field(
    AccountTokenEdges, resolver=resolve_account_tokens, limit=Int(required=False), offset=Int(required=False)
)
