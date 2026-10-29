from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.events.filters import EventNameFilter, EventRelatedFilter, EventResourceFilter
from prefect.events.filters import EventOrder as PrefectEventOrder
from prefect.events.schemas.events import ResourceSpecification

from infrahub.events.constants import EVENT_NAMESPACE, EventSortOrder
from infrahub.events.group_action import (
    GroupAutoCreateCappedEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedEvent,
)
from infrahub.task_manager.event.models import InfrahubEventFilter

if TYPE_CHECKING:
    from datetime import timedelta

    from prefect.client.orchestration import PrefectClient


class LabelEventFilter(InfrahubEventFilter):
    """Matches accounts, branch names, primary nodes, parents and the branch names of branch events by label.

    It is the reference the resource-ID filters must return the same events as.
    """

    def add_account_filter(self, account__ids: list[str] | None) -> None:
        if account__ids:
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.account", "infrahub.resource.id": account__ids}
                    )
                )
            )

    def add_branch_name_filter(self, branches: list[str] | None = None) -> None:
        if branches:
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": branches}
                    )
                )
            )

    def add_event_type_filter(
        self,
        event_type: list[str] | None = None,
        event_type_filter: dict[str, Any] | None = None,
        exclude_prefixes: list[str] | None = None,
    ) -> None:
        event_type = event_type or []
        event_type_filter = event_type_filter or {}

        if branch_merged := event_type_filter.get("branch_merged"):
            branches: list[str] = branch_merged.get("branches") or []
            if "infrahub.branch.created" not in event_type:
                event_type.append("infrahub.branch.merged")
            if branches:
                self.resource = EventResourceFilter(labels=ResourceSpecification({"infrahub.branch.name": branches}))

        if branch_migrated := event_type_filter.get("branch_migrated"):
            branches = branch_migrated.get("branches") or []
            if "infrahub.branch.created" not in event_type:
                event_type.append("infrahub.branch.migrated")
            if branches:
                self.resource = EventResourceFilter(labels=ResourceSpecification({"infrahub.branch.name": branches}))

        if branch_rebased := event_type_filter.get("branch_rebased"):
            branches = branch_rebased.get("branches") or []
            if "infrahub.branch.created" not in event_type:
                event_type.append("infrahub.branch.rebased")
            if branches:
                self.resource = EventResourceFilter(labels=ResourceSpecification({"infrahub.branch.name": branches}))

        if (group_auto_create := event_type_filter.get("group_auto_create")) is not None:
            auto_create_event_names = [
                GroupAutoCreatedEvent.event_name,
                GroupAutoCreateRejectedEvent.event_name,
                GroupAutoCreateCappedEvent.event_name,
            ]
            if not any(name in event_type for name in auto_create_event_names):
                event_type.extend(auto_create_event_names)

            resource_labels: dict[str, list[str] | str] = {}
            if idps := (group_auto_create.get("idp") or []):
                resource_labels["infrahub.security.idp"] = idps
            if protocols := (group_auto_create.get("protocol") or []):
                resource_labels["infrahub.security.protocol"] = protocols
            if resource_labels:
                self.resource = EventResourceFilter(labels=ResourceSpecification(resource_labels))

        if event_type:
            self.event = EventNameFilter(name=event_type)
        elif not event_type and exclude_prefixes:
            self.event = EventNameFilter(prefix=[f"{EVENT_NAMESPACE}."], exclude_prefix=exclude_prefixes)

    def add_primary_node_filter(self, primary_node__ids: list[str] | None) -> None:
        if primary_node__ids:
            self.resource = EventResourceFilter(labels=ResourceSpecification({"infrahub.node.id": primary_node__ids}))

    def add_parent_filter(self, parent__ids: list[str] | None) -> None:
        if parent__ids:
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.child_event", "infrahub.event_parent.id": parent__ids}
                    )
                )
            )

    @classmethod
    def from_label_filters(
        cls,
        order: EventSortOrder = EventSortOrder.DESC,
        account__ids: list[str] | None = None,
        branches: list[str] | None = None,
        primary_node__ids: list[str] | None = None,
        parent__ids: list[str] | None = None,
        event_type: list[str] | None = None,
        event_type_filter: dict[str, Any] | None = None,
    ) -> LabelEventFilter:
        filters = cls()
        filters.order = PrefectEventOrder.ASC if order == EventSortOrder.ASC else PrefectEventOrder.DESC
        filters.add_event_type_filter(event_type=event_type, event_type_filter=event_type_filter)
        filters.add_branch_name_filter(branches=branches)
        filters.add_account_filter(account__ids=account__ids)
        filters.add_parent_filter(parent__ids=parent__ids)
        filters.add_primary_node_filter(primary_node__ids=primary_node__ids)
        return filters


async def filter_events(
    client: PrefectClient,
    event_filter: InfrahubEventFilter,
    limit: int = 50,
    offset: int | None = None,
    retention: timedelta | None = None,
    include_total: bool = False,
) -> dict[str, Any]:
    """Post the filter to the task manager's event filter route and return its JSON page."""
    body: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "filter": event_filter.to_request(),
        "include_total": include_total,
    }
    if retention is not None:
        body["retention_seconds"] = int(retention.total_seconds())
    response = await client._client.post("/infrahub/events/filter", json=body)
    return response.json()


async def filter_event_ids(
    client: PrefectClient,
    event_filter: InfrahubEventFilter,
    limit: int = 50,
    offset: int | None = None,
    retention: timedelta | None = None,
) -> list[str]:
    """Return the ids of the events the task manager's event filter route returns, in its order."""
    page = await filter_events(
        client=client, event_filter=event_filter, limit=limit, offset=offset, retention=retention
    )
    return [event["id"] for event in page["events"]]
