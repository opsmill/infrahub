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
from infrahub.events.branch_action import (
    BranchCreatedEvent,
    BranchDeletedEvent,
    BranchMergedEvent,
    BranchMigratedEvent,
    BranchRebasedEvent,
)
from infrahub.events.constants import EVENT_NAMESPACE, EventSortOrder
from infrahub.events.group_action import (
    GroupAutoCreateCappedEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedEvent,
)

if TYPE_CHECKING:
    from datetime import datetime

BRANCH_NAME_RESOURCE_EVENTS = frozenset(
    {
        BranchCreatedEvent.event_name,
        BranchDeletedEvent.event_name,
        BranchMergedEvent.event_name,
        BranchMigratedEvent.event_name,
        BranchRebasedEvent.event_name,
    }
)
"""Events whose resource ID is built from the branch name."""

PRIMARY_NODE_OUTSIDE_RESOURCE_EVENTS = frozenset(
    {BranchDeletedEvent.event_name, BranchMergedEvent.event_name, GroupAutoCreatedEvent.event_name}
)
"""Events whose primary node, a proposed change or a group, is not part of their resource ID."""


class InfrahubEventFilter(EventFilter):
    def to_request(self) -> dict[str, Any]:
        """Serialize the filter for the task manager, which bounds an unset start by its activity log retention."""
        exclude = None if "since" in self.occurred.model_fields_set else {"occurred": {"since"}}
        return self.model_dump(mode="json", exclude_none=True, exclude=exclude)

    def add_related_filter(self, related: EventRelatedFilter) -> None:
        if not isinstance(self.related, list):
            self.related = []

        self.related.append(related)

    def add_account_filter(self, account__ids: list[str] | None) -> None:
        if account__ids:
            self.add_related_filter(
                EventRelatedFilter(
                    id=[f"infrahub.account.{account_id}" for account_id in account__ids], role=["infrahub.account"]
                )
            )

    def add_branch_filter(self, branch_ids: list[str] | None = None) -> None:
        if branch_ids:
            self.add_related_filter(
                EventRelatedFilter(
                    id=[f"infrahub.branch.{branch_id}" for branch_id in branch_ids], role=["infrahub.branch"]
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
        event_type = list(event_type or [])
        event_type_filter = event_type_filter or {}

        branch_names: list[str] = []
        for option, event_name in (
            ("branch_merged", BranchMergedEvent.event_name),
            ("branch_migrated", BranchMigratedEvent.event_name),
            ("branch_rebased", BranchRebasedEvent.event_name),
        ):
            if branch_option := event_type_filter.get(option):
                if BranchCreatedEvent.event_name not in event_type:
                    event_type.append(event_name)
                branch_names = branch_option.get("branches") or branch_names

        resource_labels: dict[str, list[str] | str] = {}
        if (group_auto_create := event_type_filter.get("group_auto_create")) is not None:
            auto_create_event_names = [
                GroupAutoCreatedEvent.event_name,
                GroupAutoCreateRejectedEvent.event_name,
                GroupAutoCreateCappedEvent.event_name,
            ]
            if not any(name in event_type for name in auto_create_event_names):
                event_type.extend(auto_create_event_names)

            if idps := (group_auto_create.get("idp") or []):
                resource_labels["infrahub.security.idp"] = idps
            if protocols := (group_auto_create.get("protocol") or []):
                resource_labels["infrahub.security.protocol"] = protocols

        if resource_labels:
            self.resource = EventResourceFilter(labels=ResourceSpecification(resource_labels))
        elif branch_names:
            self.resource = self._branch_name_resource_filter(branch_names=branch_names, event_names=event_type)

        if event_type:
            self.event = EventNameFilter(name=event_type)
        elif not event_type and exclude_prefixes:
            self.event = EventNameFilter(prefix=[f"{EVENT_NAMESPACE}."], exclude_prefix=exclude_prefixes)

    @staticmethod
    def _branch_name_resource_filter(branch_names: list[str], event_names: list[str]) -> EventResourceFilter:
        if set(event_names) <= BRANCH_NAME_RESOURCE_EVENTS:
            return EventResourceFilter(id=[f"infrahub.branch.{name}" for name in branch_names])
        # Other events also carry the branch name on their resource, but not in its ID.
        return EventResourceFilter(labels=ResourceSpecification({"infrahub.branch.name": branch_names}))

    def add_primary_node_filter(self, primary_node__ids: list[str] | None) -> None:
        """Match the indexed resource ID too when the event types, set beforehand, all keep the node ID in it."""
        if not primary_node__ids:
            return

        labels: dict[str, list[str] | str] = {"infrahub.node.id": primary_node__ids}
        listed_events = set(self.event.name or []) if self.event else set()
        if listed_events and not listed_events & PRIMARY_NODE_OUTSIDE_RESOURCE_EVENTS:
            labels = {
                "prefect.resource.id": [
                    resource_id
                    for node_id in primary_node__ids
                    for resource_id in (
                        f"infrahub.node.{node_id}",
                        node_id,
                        f"infrahub.account.{node_id}",
                        f"infrahub.proposed_change.{node_id}",
                    )
                ],
                **labels,
            }
        self.resource = EventResourceFilter(labels=ResourceSpecification(labels))

    def add_parent_filter(self, parent__ids: list[str] | None) -> None:
        if parent__ids:
            self.add_related_filter(EventRelatedFilter(id=parent__ids, role=["infrahub.ancestor_event"]))
            # Ancestors include grandparents, so the label keeps only the direct children.
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.child_event", "infrahub.event_parent.id": parent__ids}
                    )
                )
            )

    def add_related_node_filter(self, related_node__ids: list[str] | None) -> None:
        if related_node__ids:
            # Group members and ancestors are related nodes of the event, but they
            # carry their own roles rather than the generic one. Matching all three
            # roles keeps this filter correct for both the consolidated group event
            # format and any older events still listing members as related nodes.
            self.add_related_filter(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {
                            "prefect.resource.role": [
                                "infrahub.related.node",
                                "infrahub.group.member",
                                "infrahub.group.ancestor",
                            ],
                            "prefect.resource.id": related_node__ids,
                        }
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
        branch_ids: list[str] | None = None,
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
        filters.add_branch_filter(branch_ids=branch_ids)
        filters.add_account_filter(account__ids=account__ids)
        filters.add_parent_filter(parent__ids=parent__ids)
        filters.add_primary_node_filter(primary_node__ids=primary_node__ids)
        filters.add_related_node_filter(related_node__ids=related_node__ids)

        return filters
