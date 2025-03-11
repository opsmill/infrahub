from __future__ import annotations

import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Any
from uuid import UUID

from prefect.client.schemas.objects import Log as PrefectLog  # noqa: TC002
from prefect.events.filters import (
    EventFilter,
    EventIDFilter,
    EventNameFilter,
    EventOccurredFilter,
    EventRelatedFilter,
    EventResourceFilter,
)
from prefect.events.schemas.events import ResourceSpecification
from pydantic import BaseModel, Field

from infrahub.core.timestamp import Timestamp

from .constants import LOG_LEVEL_MAPPING

if TYPE_CHECKING:
    from datetime import datetime


class RelatedNodeInfo(BaseModel):
    id: str
    kind: str | None = None


class RelatedNodesInfo(BaseModel):
    flows: dict[UUID, dict[str, RelatedNodeInfo]] = Field(default_factory=lambda: defaultdict(dict))  # type: ignore[arg-type]
    nodes: dict[str, RelatedNodeInfo] = Field(default_factory=dict)

    def add_nodes(self, flow_id: UUID, node_ids: list[str]) -> None:
        for node_id in node_ids:
            self.add_node(flow_id=flow_id, node_id=node_id)

    def add_node(self, flow_id: UUID, node_id: str) -> None:
        if node_id not in self.nodes:
            node = RelatedNodeInfo(id=node_id)
            self.nodes[node_id] = node
        self.flows[flow_id][node_id] = self.nodes[node_id]

    def get_related_nodes(self, flow_id: UUID) -> list[RelatedNodeInfo]:
        if flow_id not in self.flows or len(self.flows[flow_id].keys()) == 0:
            return []
        return list(self.flows[flow_id].values())

    def get_related_nodes_as_dict(self, flow_id: UUID) -> list[dict[str, str | None]]:
        if flow_id not in self.flows or len(self.flows[flow_id].keys()) == 0:
            return []
        return [item.model_dump() for item in list(self.flows[flow_id].values())]

    def get_first_related_node(self, flow_id: UUID) -> RelatedNodeInfo | None:
        if nodes := self.get_related_nodes(flow_id=flow_id):
            return nodes[0]
        return None

    def get_unique_related_node_ids(self) -> list[str]:
        return list(self.nodes.keys())


class FlowLogs(BaseModel):
    logs: defaultdict[UUID, list[PrefectLog]] = Field(default_factory=lambda: defaultdict(list))  # type: ignore[arg-type]

    def to_graphql(self, flow_id: UUID) -> list[dict]:
        return [
            {
                "node": {
                    "message": log.message,
                    "severity": LOG_LEVEL_MAPPING.get(log.level, "error"),
                    "timestamp": log.timestamp.to_iso8601_string(),
                }
            }
            for log in self.logs[flow_id]
        ]


class FlowProgress(BaseModel):
    data: dict[UUID, float] = Field(default_factory=dict)


class InfrahubEventFilter(EventFilter):
    matching_related: list[EventRelatedFilter] = Field(default_factory=list)

    def add_account_filter(self, account__ids: list[str] | None) -> None:
        if account__ids:
            self.matching_related.append(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.account", "infrahub.resource.id": account__ids}
                    )
                )
            )

    def add_branch_filter(self, branches: list[str] | None = None) -> None:
        if branches:
            self.matching_related.append(
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
            self.matching_related.append(EventRelatedFilter(labels=ResourceSpecification(event_filter)))

    def add_event_id_filter(self, ids: list[str] | None = None) -> None:
        if ids:
            self.id = EventIDFilter(id=[uuid.UUID(id) for id in ids])

    def add_event_type_filter(
        self, event_type: list[str] | None = None, event_type_filter: dict[str, Any] | None = None
    ) -> None:
        event_type = event_type or []
        event_type_filter = event_type_filter or {}

        if branch_merged := event_type_filter.get("branch_merged"):
            branches: list[str] = branch_merged.get("branches") or []
            if "infrahub.branch.created" not in event_type:
                event_type.append("infrahub.branch.merged")
            if branches:
                self.resource = EventResourceFilter(labels=ResourceSpecification({"infrahub.branch.name": branches}))

        if branch_rebased := event_type_filter.get("branch_rebased"):
            branches = branch_rebased.get("branches") or []
            if "infrahub.branch.created" not in event_type:
                event_type.append("infrahub.branch.rebased")
            if branches:
                self.resource = EventResourceFilter(labels=ResourceSpecification({"infrahub.branch.name": branches}))

        if event_type:
            self.event = EventNameFilter(name=event_type)

    def add_primary_node_filter(self, primary_node__ids: list[str] | None) -> None:
        if primary_node__ids:
            self.resource = EventResourceFilter(labels=ResourceSpecification({"infrahub.node.id": primary_node__ids}))

    def add_parent_filter(self, parent__ids: list[str] | None) -> None:
        if parent__ids:
            self.matching_related.append(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.child_event", "infrahub.event_parent.id": parent__ids}
                    )
                )
            )

    def add_related_node_filter(self, related_node__ids: list[str] | None) -> None:
        if related_node__ids:
            self.matching_related.append(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.related.node", "prefect.resource.id": related_node__ids}
                    )
                )
            )

    @classmethod
    def from_filters(
        cls,
        ids: list[str] | None = None,
        account__ids: list[str] | None = None,
        related_node__ids: list[str] | None = None,
        parent__ids: list[str] | None = None,
        primary_node__ids: list[str] | None = None,
        event_type: list[str] | None = None,
        event_type_filter: dict[str, Any] | None = None,
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

        filters.add_event_filter(level=level, has_children=has_children)
        filters.add_event_id_filter(ids=ids)
        filters.add_event_type_filter(event_type=event_type, event_type_filter=event_type_filter)
        filters.add_branch_filter(branches=branches)
        filters.add_account_filter(account__ids=account__ids)
        filters.add_parent_filter(parent__ids=parent__ids)
        filters.add_primary_node_filter(primary_node__ids=primary_node__ids)
        filters.add_related_node_filter(related_node__ids=related_node__ids)

        return filters
