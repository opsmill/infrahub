from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.query.relationship import RelationshipGetByIdentifierQuery
from infrahub.graphql.types import RelationshipNode

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class Relationships(ObjectType):
    edges = List(of_type=NonNull(RelationshipNode), required=True)
    count = Int(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        ids: list[str],
        limit: int = 10,
        offset: int = 0,
        excluded_namespaces: list[str] | None = None,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context

        fields = await extract_fields_first_node(info)
        excluded_namespaces = excluded_namespaces or []

        response: dict[str, Any] = {"edges": [], "count": None}

        async with graphql_context.db.start_session(read_only=True) as db:
            query = await RelationshipGetByIdentifierQuery.init(
                db=db,
                branch=graphql_context.branch,
                at=graphql_context.at,
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
    ids=List(NonNull(String), required=True),
    excluded_namespaces=List(String),
    limit=Int(required=False),
    offset=Int(required=False),
    resolver=Relationships.resolve,
    required=True,
)
