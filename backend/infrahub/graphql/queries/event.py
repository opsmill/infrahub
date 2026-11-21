from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Argument, Boolean, DateTime, Enum, Field, Int, List, NonNull, ObjectType, String

from infrahub.core.constants import GlobalPermissions
from infrahub.core.query.branch import BranchGetIdsByNameQuery
from infrahub.events.constants import ACCOUNT_EVENT_PREFIX, EventSortOrder
from infrahub.exceptions import PermissionDeniedError, ValidationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types.event import EventNodes, EventTypeFilter
from infrahub.permissions import define_global_permission_from_branch
from infrahub.task_manager.event.models import InfrahubEventFilter
from infrahub.task_manager.event.query import PrefectEvent

if TYPE_CHECKING:
    from datetime import datetime

    from graphql import GraphQLResolveInfo

    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


InfrahubEventSortOrder = Enum.from_enum(EventSortOrder)

MATCH_PATTERN_CHARACTERS = frozenset("*?")
"""Characters that the task manager reads as wildcards in a label match, which the ID filters do not use."""

NEGATED_MATCH_PREFIX = "!"
"""The prefix that the task manager reads as a negation in a label match."""


def _reject_match_patterns(parameter: str, values: list[str] | None, names_may_start_with_negation: bool) -> None:
    """Refuse a value that only a label match reads as a pattern, because the exact ID filter would match no event.

    Raises:
        ValidationError: When a value contains a wildcard, or starts with the negation prefix where names cannot.

    """
    for value in values or []:
        negated = value.startswith(NEGATED_MATCH_PREFIX) and not names_may_start_with_negation
        if negated or MATCH_PATTERN_CHARACTERS.intersection(value):
            raise ValidationError(
                input_value=f"The parameter '{parameter}' takes exact values, not match patterns: '{value}'"
            )


async def _current_branch_ids(db: InfrahubDatabase, names: list[str]) -> dict[str, str]:
    query = await BranchGetIdsByNameQuery.init(db=db, names=[name for name in names if name])
    await query.execute(db=db)
    return {branch.name: branch.uuid for branch in query.get_data()}


class Events(ObjectType):
    edges = List(NonNull(EventNodes), required=True)
    count = Int(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        order: EventSortOrder,
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
        if offset is not None and offset < 0:
            raise ValidationError(input_value="The parameter 'offset' can't be negative")
        _reject_match_patterns(parameter="account__ids", values=account__ids, names_may_start_with_negation=False)
        _reject_match_patterns(parameter="parent__ids", values=parent__ids, names_may_start_with_negation=False)
        # A branch name may start with the negation prefix, and is resolved to its ID before the query.
        _reject_match_patterns(parameter="branches", values=branches, names_may_start_with_negation=True)

        exclude_prefixes: list[str] | None = None
        graphql_context: GraphqlContext = info.context

        if event_type and any(et.startswith(ACCOUNT_EVENT_PREFIX) for et in event_type):
            graphql_context.active_permissions.raise_for_permission(
                permission=define_global_permission_from_branch(
                    permission=GlobalPermissions.MANAGE_ACCOUNTS,
                    branch_name=graphql_context.branch.name,
                )
            )
        elif not event_type:
            try:
                graphql_context.active_permissions.raise_for_permission(
                    permission=define_global_permission_from_branch(
                        permission=GlobalPermissions.MANAGE_ACCOUNTS,
                        branch_name=graphql_context.branch.name,
                    )
                )
            except PermissionDeniedError:
                exclude_prefixes = [ACCOUNT_EVENT_PREFIX]

        branch_ids: list[str] | None = None
        if branches:
            async with graphql_context.db.start_session(read_only=True) as db:
                current_branch_ids = await _current_branch_ids(db=db, names=branches)
            branch_ids = await PrefectEvent.resolve_branch_ids(
                names=branches,
                current_branch_ids=current_branch_ids,
            )
            if not branch_ids:
                return {"count": 0, "edges": []}

        event_filter = InfrahubEventFilter.from_filters(
            ids=ids,
            branch_ids=branch_ids,
            account__ids=account__ids,
            has_children=has_children,
            event_type=event_type,
            event_type_filter=event_type_filter,
            related_node__ids=related_node__ids,
            parent__ids=parent__ids,
            since=since,
            until=until,
            level=level,
            order=order,
            exclude_prefixes=exclude_prefixes,
        )

        return await Events.query(
            info=info,
            event_filters=event_filter.for_primary_nodes(
                primary_node__ids=primary_node__ids, page_end=(offset or 0) + limit
            ),
            limit=limit,
            offset=offset,
        )

    @classmethod
    async def query(
        cls,
        info: GraphQLResolveInfo,
        event_filters: list[InfrahubEventFilter],
        limit: int,
        offset: int | None = None,
    ) -> dict[str, Any]:
        fields = extract_graphql_fields(info)

        prefect_tasks = await PrefectEvent.query(
            fields=fields,
            event_filters=event_filters,
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
    since=DateTime(
        required=False,
        description=(
            "Search events since this timestamp, defaults to the activity log retention before until, "
            "and at least 180 days before until; a query by ids or parent__ids has no default start"
        ),
    ),
    until=DateTime(required=False, description="Search events until this timestamp, defaults to the current time"),
    branches=List(NonNull(String), required=False, description="Filter the query to specific branches"),
    account__ids=List(NonNull(String), required=False, description="Filter the query to specific accounts"),
    ids=List(NonNull(String)),
    order=InfrahubEventSortOrder(
        required=False,
        default_value=EventSortOrder.DESC,
        description="Sort order of the events, defaults to descending order",
    ),
    resolver=Events.resolve,
    required=True,
)
