from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from graphene import Argument, Boolean, DateTime, Enum, Field, Int, List, NonNull, ObjectType, String

from infrahub.core import registry
from infrahub.core.constants import GlobalPermissions, NodeProperty
from infrahub.core.ownership.fields import (
    ATTRIBUTE_OWNERS_PROPERTY,
    FIELD_OWNERS_SUFFIX,
    NODE_SOURCES_FIELD,
    OWNER_LABEL_SEPARATOR,
    OWNERS_CHANGELOG_KIND,
    deleted_label,
    is_owners_field_name,
    owner_ids_from_value,
    owner_list_value,
)
from infrahub.events.constants import ACCOUNT_EVENT_PREFIX, EventSortOrder
from infrahub.exceptions import BranchNotFoundError, PermissionDeniedError, ValidationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types.event import EventNodes, EventTypeFilter
from infrahub.permissions import define_global_permission_from_branch
from infrahub.task_manager.event.models import InfrahubEventFilter
from infrahub.task_manager.event.query import PrefectEvent

if TYPE_CHECKING:
    from datetime import datetime

    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.graphql.initialization import GraphqlContext


InfrahubEventSortOrder = Enum.from_enum(EventSortOrder)
OWNER_VALUE_KEYS = ("value", "value_previous")


def _single_owner_list(owner_id: str | None) -> str | None:
    return owner_list_value(owner_ids=(owner_id,)) if owner_id else None


def _attribute_owner_changes(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one change under `<attribute>__owners` for each attribute of a mutated node whose owners changed.

    The event stores the owners of an attribute as a property in its payload only: the `owners` property with the
    owner lists, or the `owner` property with one owner ID for a change between no owner and one owner.
    """
    changelog = ((node.get("payload") or {}).get("data") or {}).get("changelog") or {}
    changes: list[dict[str, Any]] = []
    for name, attribute in (changelog.get("attributes") or {}).items():
        properties = attribute.get("properties") or {}
        if owners := properties.get(ATTRIBUTE_OWNERS_PROPERTY):
            value, value_previous = owners["value"], owners["value_previous"]
        elif owners := properties.get(NodeProperty.OWNER.value):
            value, value_previous = _single_owner_list(owners["value"]), _single_owner_list(owners["value_previous"])
        else:
            continue
        changes.append(
            {
                "name": f"{name}{FIELD_OWNERS_SUFFIX}",
                "kind": OWNERS_CHANGELOG_KIND,
                "value": value,
                "value_previous": value_previous,
                "action": owners["value_update_status"],
            }
        )
    return changes


async def _show_owner_labels(graphql_context: GraphqlContext, edges: list[dict[str, Any]]) -> None:
    """Replace the IDs of each change of an owner list or a source list with the display labels that the nodes have now.

    The event stores the IDs, so that a rename of an owner shows in the log of all its earlier changes.
    """
    for edge in edges:
        if "attributes" in edge["node"]:
            edge["node"]["attributes"].extend(_attribute_owner_changes(node=edge["node"]))
    # A source can exist on one branch only, so the labels of the changes of an event come from the branch of the event.
    branches: dict[str, Branch] = {}
    changes_by_branch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        changes = [
            attribute
            for attribute in edge["node"].get("attributes") or []
            if attribute["kind"] == OWNERS_CHANGELOG_KIND and is_owners_field_name(field_name=attribute["name"])
        ]
        if changes:
            branch = _event_branch(graphql_context=graphql_context, branch_name=edge["node"]["branch"])
            branches[branch.name] = branch
            changes_by_branch[branch.name].extend(changes)
    await asyncio.gather(
        *(
            _show_labels_on_branch(graphql_context=graphql_context, branch=branches[name], changes=changes)
            for name, changes in changes_by_branch.items()
        )
    )


def _event_branch(graphql_context: GraphqlContext, branch_name: str | None) -> Branch:
    """Return the branch of an event, or the branch of the request for a global event or a deleted branch."""
    if branch_name is None:
        return graphql_context.branch
    try:
        return registry.get_branch_from_registry(branch=branch_name)
    except BranchNotFoundError:
        return graphql_context.branch


async def _show_labels_on_branch(
    graphql_context: GraphqlContext, branch: Branch, changes: list[dict[str, Any]]
) -> None:
    node_ids = sorted(
        {
            node_id
            for change in changes
            for key in OWNER_VALUE_KEYS
            for node_id in owner_ids_from_value(value=change[key]) or []
        }
    )
    if not node_ids:
        return
    references = await graphql_context.ownership_resolver.load_metadata_nodes(
        context=graphql_context, node_ids=node_ids, branch=branch
    )
    labels = {
        reference.id: reference.display_label or reference.id for reference in references if not reference.is_deleted
    }
    for change in changes:
        deleted = deleted_label(is_source=change["name"] == NODE_SOURCES_FIELD)
        for key in OWNER_VALUE_KEYS:
            listed_ids = owner_ids_from_value(value=change[key])
            if listed_ids is not None:
                change[key] = OWNER_LABEL_SEPARATOR.join(labels.get(node_id, deleted) for node_id in listed_ids)


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
            order=order,
            exclude_prefixes=exclude_prefixes,
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
        fields = extract_graphql_fields(info)

        prefect_tasks = await PrefectEvent.query(
            fields=fields,
            event_filter=event_filter,
            limit=limit,
            offset=offset,
        )
        edges = prefect_tasks.get("edges", [])
        await _show_owner_labels(graphql_context=info.context, edges=edges)
        return {
            "count": prefect_tasks.get("count", 0),
            "edges": edges,
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
    order=InfrahubEventSortOrder(
        required=False,
        default_value=EventSortOrder.DESC,
        description="Sort order of the events, defaults to descending order",
    ),
    resolver=Events.resolve,
    required=True,
)
