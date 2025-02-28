from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Argument, Boolean, DateTime, Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.exceptions import ValidationError
from infrahub.graphql.types.event import EventNodes, EventTypeFilter
from infrahub.task_manager.event import PrefectEvent
from infrahub.task_manager.models import InfrahubEventFilter

if TYPE_CHECKING:
    from datetime import datetime

    from graphql import GraphQLResolveInfo


class Events(ObjectType):
    edges = List(NonNull(EventNodes), required=True)
    count = Int(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        limit: int = 10,
        has_children: bool | None = None,
        level: int | None = None,
        offset: int | None = None,
        account__ids: list[str] | None = None,
        ids: list[str] | None = None,
        branches: list[str] | None = None,
        event_type: list[str] | None = None,
        event_type_filter: dict[str, Any] | None = None,
        related_node__ids: list[str] | None = None,
        primary_node__ids: list[str] | None = None,
        parent__ids: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        ids = ids or []
        if limit > 50:
            # Prefect restricts this to 50
            raise ValidationError(input_value="The parameter 'limit' can't be above 50")

        event_filter = InfrahubEventFilter.from_filters(
            ids=ids,
            branches=branches,
            account__ids=account__ids,
            has_children=has_children,
            event_type=event_type,
            event_type_filter=event_type_filter,
            related_node__ids=related_node__ids,
            primary_node__ids=primary_node__ids,
            parent__ids=parent__ids,
            since=since,
            until=until,
            level=level,
        )

        return await Events.query(
            info=info,
            event_filter=event_filter,
            limit=limit,
            offset=offset,
        )

    @classmethod
    async def query(
        cls,
        info: GraphQLResolveInfo,
        event_filter: InfrahubEventFilter,
        limit: int,
        offset: int | None = None,
    ) -> dict[str, Any]:
        fields = await extract_fields_first_node(info)

        prefect_tasks = await PrefectEvent.query(
            fields=fields,
            event_filter=event_filter,
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
    level=Int(required=False),
    has_children=Boolean(required=False, description="Filter events based on if they can have children or not"),
    event_type=List(NonNull(String), description="Filter events that match a specific type"),
    event_type_filter=Argument(EventTypeFilter, required=False, description="Filters specific to a given event_type"),
    primary_node__ids=List(
        NonNull(String), description="Filter events where the primary node id is within indicated node ids"
    ),
    related_node__ids=List(
        NonNull(String), description="Filter events where the related node ids are within indicated node ids"
    ),
    parent__ids=List(
        NonNull(String), description="Search events that has any of the indicated event ids listed as parents"
    ),
    since=DateTime(required=False, description="Search events since this timestamp, defaults to 180 days back"),
    until=DateTime(required=False, description="Search events until this timestamp, defaults the current time"),
    branches=List(NonNull(String), required=False, description="Filter the query to specific branches"),
    account__ids=List(NonNull(String), required=False, description="Filter the query to specific accounts"),
    ids=List(NonNull(String)),
    resolver=Events.resolve,
    required=True,
)
