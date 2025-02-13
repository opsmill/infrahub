from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.exceptions import ValidationError
from infrahub.graphql.types.event import EventNodes
from infrahub.task_manager.event import PrefectEvent

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


class Events(ObjectType):
    edges = List(NonNull(EventNodes), required=True)
    count = Int(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        limit: int = 10,
        offset: int | None = None,
        account: str | None = None,
        ids: list[str] | None = None,
        branch: str | None = None,
        q: str | None = None,
        related_node__ids: list[str] | None = None,
    ) -> dict[str, Any]:
        ids = ids or []
        if limit > 50:
            # Prefect restricts this to 50
            raise ValidationError(input_value="The parameter 'limit' can't be above 50")
        return await Events.query(
            info=info,
            branch=branch,
            account=account,
            limit=limit,
            offset=offset,
            related_node__ids=related_node__ids,
            q=q,
            ids=ids,
        )

    @classmethod
    async def query(
        cls,
        info: GraphQLResolveInfo,
        limit: int,
        offset: int | None = None,
        q: str | None = None,
        ids: list[str] | None = None,
        related_node__ids: list[str] | None = None,
        branch: str | None = None,
        account: str | None = None,
    ) -> dict[str, Any]:
        fields = await extract_fields_first_node(info)

        prefect_tasks = await PrefectEvent.query(
            fields=fields,
            q=q,
            ids=ids,
            related_node__ids=related_node__ids,
            branch=branch,
            account=account,
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
    account=String(required=False),
    ids=List(String),
    q=String(required=False),
    resolver=Events.resolve,
    required=True,
)
