from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from graphene import Field, Int, List, ObjectType, String
from infrahub_sdk.utils import extract_fields, extract_fields_first_node

from infrahub.core.query.relationship import RelationshipGetByIdentifierQuery
from infrahub.graphql.types import RelationshipNode

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext


class Relationships(ObjectType):
    edges = List(RelationshipNode)
    count = Int()

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        limit: int = 10,
        offset: int = 0,
        ids: List[str] = [],
    ) -> Dict[str, Any]:
        context: GraphqlContext = info.context

        fields = await extract_fields_first_node(info)

        response: Dict[str, Any] = {"edges": [], "count": None}

        async with context.db.start_session() as db:
            query = await RelationshipGetByIdentifierQuery.init(
                db=db, branch=context.branch, at=context.at, identifiers=ids, limit=limit, offset=offset
            )

            if "count" in fields:
                response["count"] = await query.count(db=db)

            if not fields:
                return response

            await query.execute(db=db)

            nodes = []
            for peers in query.get_peers():
                nodes.append(
                    {
                        "node": {
                            "id": peers.id,
                            "peers": [
                                {"id": peers.source_id, "kind": peers.source_kind},
                                {"id": peers.destination_id, "kind": peers.destination_kind},
                            ],
                        }
                    }
                )
            response["edges"] = nodes

            return response


Relationship = Field(
    Relationships,
    resolver=Relationships.resolve,
    limit=Int(required=False),
    offset=Int(required=False),
    ids=List(String),
)
