from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from prefect.events.filters import (
    EventFilter,
    EventIDFilter,
    EventNameFilter,
    EventOccurredFilter,
    EventRelatedFilter,
    EventResourceFilter,
)
from prefect.events.filters import EventOrder as PrefectEventOrder
from prefect.events.schemas.events import ResourceSpecification

from infrahub.core.timestamp import Timestamp
from infrahub.events.constants import EVENT_NAMESPACE, EventSortOrder
from infrahub.events.group_action import (
    GroupAutoCreateCappedEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedEvent,
)

if TYPE_CHECKING:
    from datetime import datetime


class InfrahubEventFilter(EventFilter):
    def add_related_filter(self, related: EventRelatedFilter) -> None:
        if not isinstance(self.related, list):
            self.related = []

        self.related.append(related)

    def add_account_filter(self, account__ids: list[str] | None) -> None:
        if account__ids:
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.account", "infrahub.resource.id": account__ids}
                    )
                )
            )

    def add_branch_filter(self, branches: list[str] | None = None) -> None:
        if branches:
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": branches}
                    )
                )
            )

    def add_event_filter(self, level: int | None = None, has_children: bool | None = None) -> None:
        event_filter: dict[str, list[str] | str] = {}
        if level is not None:
            event_filter["infrahub.event.level"] = str(level)

        if has_children is not None:
            event_filter["infrahub.event.has_children"] = str(has_children).lower()

        if event_filter:
            event_filter["prefect.resource.role"] = "infrahub.event"
            self.add_related_filter(EventRelatedFilter(labels=ResourceSpecification(event_filter)))

    def add_event_id_filter(self, ids: list[str] | None = None) -> None:
        if ids:
            self.id = EventIDFilter(id=[uuid.UUID(id) for id in ids])

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

    def add_related_node_filter(self, related_node__ids: list[str] | None) -> None:
        if related_node__ids:
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.related.node", "prefect.resource.id": related_node__ids}
                    )
                )
            )

    @classmethod
    def from_filters(
        cls,
        order: EventSortOrder,
        ids: list[str] | None = None,
        account__ids: list[str] | None = None,
        related_node__ids: list[str] | None = None,
        parent__ids: list[str] | None = None,
        primary_node__ids: list[str] | None = None,
        event_type: list[str] | None = None,
        event_type_filter: dict[str, Any] | None = None,
        exclude_prefixes: list[str] | None = None,
        branches: list[str] | None = None,
        level: int | None = None,
        has_children: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> InfrahubEventFilter:
        occurred_filter = {}
        if since:
            occurred_filter["since"] = Timestamp(since.isoformat()).to_datetime()

        if until:
            occurred_filter["until"] = Timestamp(until.isoformat()).to_datetime()

        if occurred_filter:
            filters = cls(occurred=EventOccurredFilter(**occurred_filter))
        else:
            filters = cls()

        match order:
            case EventSortOrder.ASC:
                filters.order = PrefectEventOrder.ASC
            case EventSortOrder.DESC:
                filters.order = PrefectEventOrder.DESC

        filters.add_event_filter(level=level, has_children=has_children)
        filters.add_event_id_filter(ids=ids)
        filters.add_event_type_filter(
            event_type=event_type, event_type_filter=event_type_filter, exclude_prefixes=exclude_prefixes
        )
        filters.add_branch_filter(branches=branches)
        filters.add_account_filter(account__ids=account__ids)
        filters.add_parent_filter(parent__ids=parent__ids)
        filters.add_primary_node_filter(primary_node__ids=primary_node__ids)
        filters.add_related_node_filter(related_node__ids=related_node__ids)

        return filters
