from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from graphene import Boolean, Field, Int, List, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node, is_valid_uuid

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.protocols import CoreNode
    from infrahub.graphql.initialization import GraphqlContext


class Node(ObjectType):
    id = Field(String, required=True)
    kind = Field(String, required=True, description="The node kind")


class NodeEdge(ObjectType):
    node = Field(Node, required=True)


class NodeEdges(ObjectType):
    count = Field(Int, required=True)
    edges = Field(List(of_type=NodeEdge, required=True), required=False)


async def search_resolver(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
    q: str,
    limit: int = 10,
    partial_match: bool = True,
) -> dict[str, Any]:
    context: GraphqlContext = info.context
    response: dict[str, Any] = {}
    result: list[CoreNode] = []

    fields = await extract_fields_first_node(info)

    if is_valid_uuid(q):
        matching: Optional[CoreNode] = await NodeManager.get_one(
            db=context.db, branch=context.branch, at=context.at, id=q
        )
        if matching:
            result.append(matching)
    else:
        result.extend(
            await NodeManager.query(
                db=context.db,
                branch=context.branch,
                schema=InfrahubKind.NODE,
                filters={"any__value": q},
                limit=limit,
                partial_match=partial_match,
            )
        )

    if "edges" in fields and result:
        response["edges"] = [{"node": {"id": obj.id, "kind": obj.get_kind()}} for obj in result]

    if "count" in fields:
        response["count"] = len(result)

    return response


InfrahubSearchAnywhere = Field(
    NodeEdges,
    q=String(required=True),
    limit=Int(required=False),
    partial_match=Boolean(required=False),
    resolver=search_resolver,
)
