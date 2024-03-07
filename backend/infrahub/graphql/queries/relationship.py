from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from graphene import Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

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
        ids: List[str],
        limit: int = 10,
        offset: int = 0,
        excluded_namespaces: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        context: GraphqlContext = info.context

        fields = await extract_fields_first_node(info)
        excluded_namespaces = excluded_namespaces or []

        response: Dict[str, Any] = {"edges": [], "count": None}

        async with context.db.start_session() as db:
            query = await RelationshipGetByIdentifierQuery.init(
                db=db,
                branch=context.branch,
                at=context.at,
                identifiers=ids,
                excluded_namespaces=excluded_namespaces,
                limit=limit,
                offset=offset,
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
                            "identifier": peers.identifier,
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
    ids=List(NonNull(String), required=True),
    excluded_namespaces=List(String),
)
