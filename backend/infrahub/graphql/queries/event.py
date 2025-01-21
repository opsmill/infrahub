from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.graphql.types.event import EventNodes
from infrahub.task_manager.event import PrefectEvent

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


class Events(ObjectType):
    edges = List(NonNull(EventNodes), required=True)
    count = Int(required=True)

    @staticmethod
    async def resolve(
        root: dict,
        info: GraphQLResolveInfo,
        limit: int = 10,
        offset: int = 0,
        ids: list[str] | None = None,
        branch: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        # related_nodes = related_node__ids or []
        ids = ids or []
        return await Events.query(
            info=info,
            branch=branch,
            limit=limit,
            offset=offset,
            q=q,
            ids=ids,
        )

    @classmethod
    async def query(
        cls,
        info: GraphQLResolveInfo,
        q: str | None = None,
        ids: list[str] | None = None,
        branch: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        fields = await extract_fields_first_node(info)

        prefect_tasks = await PrefectEvent.query(
            fields=fields,
            q=q,
            ids=ids,
            branch=branch,
            limit=limit,
            offset=offset,
        )
        return {
            "count": prefect_tasks.get("count", 0),
            "edges": prefect_tasks.get("edges", []),
        }


Event = Field(
    Events,
    limit=Int(required=False),
    offset=Int(required=False),
    related_node__ids=List(String),
    branch=String(required=False),
    ids=List(String),
    q=String(required=False),
    resolver=Events.resolve,
    required=True,
)
