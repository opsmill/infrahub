from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from prefect.client.orchestration import PrefectClient, get_client
from prefect.events.filters import (
    EventFilter,
    EventIDFilter,
    EventNameFilter,
    EventOccurredFilter,
    EventRelatedFilter,
    EventResourceFilter,
)
from prefect.events.schemas.events import Event as PrefectEventModel
from prefect.events.schemas.events import ResourceSpecification
from pydantic import BaseModel, Field, TypeAdapter

from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.utils import get_nested_dict

log = get_logger()

if TYPE_CHECKING:
    from datetime import datetime


class InfrahubEventFilter(EventFilter):
    matching_related: list[EventRelatedFilter] = Field(default_factory=list)

    def add_account_filter(self, account: list[str] | None) -> None:
        if account:
            self.matching_related.append(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.account", "infrahub.resource.id": account}
                    )
                )
            )

    def add_branch_filter(self, branch: list[str] | None = None) -> None:
        if branch:
            self.matching_related.append(
                EventRelatedFilter(
                    labels=ResourceSpecification(
                        {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": branch}
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

    def add_event_type_filter(self, event_type: list[str] | None = None) -> None:
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
        account: list[str] | None = None,
        related_node__ids: list[str] | None = None,
        parent__ids: list[str] | None = None,
        primary_node__ids: list[str] | None = None,
        event_type: list[str] | None = None,
        branch: list[str] | None = None,
        level: int | None = None,
        has_children: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> InfrahubEventFilter:
        occurred_filter = {}
        if since:
            occurred_filter["since"] = Timestamp(since.isoformat()).obj

        if until:
            occurred_filter["until"] = Timestamp(until.isoformat()).obj

        if occurred_filter:
            filters = cls(occurred=EventOccurredFilter(**occurred_filter))
        else:
            filters = cls()

        filters.add_event_filter(level=level, has_children=has_children)
        filters.add_event_id_filter(ids=ids)
        filters.add_event_type_filter(event_type=event_type)
        filters.add_branch_filter(branch=branch)
        filters.add_account_filter(account=account)
        filters.add_parent_filter(parent__ids=parent__ids)
        filters.add_primary_node_filter(primary_node__ids=primary_node__ids)
        filters.add_related_node_filter(related_node__ids=related_node__ids)

        return filters


class PrefectEventData(PrefectEventModel):
    def get_branch(self) -> str | None:
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.branch":
                continue
            if "infrahub.resource.label" not in resource:
                continue
            return resource.get("infrahub.resource.label")
        return None

    def get_level(self) -> int:
        for resource in self.related:
            level = resource.get("infrahub.event.level")
            if level is None:
                continue
            try:
                return int(level)
            except ValueError:
                return 0

        return 0

    def get_parent(self) -> str | None:
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.child_event":
                continue
            return resource.get("infrahub.event_parent.id")
        return None

    def get_primary_node(self) -> dict[str, str] | None:
        node_id = self.resource.get("infrahub.node.id")
        node_kind = self.resource.get("infrahub.node.kind")
        if node_id and node_kind:
            return {"id": node_id, "kind": node_kind}

        return None

    def get_related_nodes(self) -> list[dict[str, str]]:
        related_nodes = []
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.related.node":
                continue

            node_id = resource.get("prefect.resource.id")
            node_kind = resource.get("infrahub.node.kind")
            if node_id == self.resource.get("infrahub.node.id"):
                # Don't include the primary node as a related node.
                continue
            if node_id and node_kind:
                related_nodes.append({"id": node_id, "kind": node_kind})

        return related_nodes

    def get_account_id(self) -> str | None:
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.account":
                continue
            return resource.get("infrahub.resource.id")
        return None

    def has_children(self) -> bool:
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.event":
                continue
            if resource.get("infrahub.event.has_children") == "true":
                return True
            return False
        return False

    def _return_node_mutation(self) -> dict[str, Any]:
        attributes = []

        for resource in self.related:
            if resource.get("prefect.resource.role") == "infrahub.node.field_update" and resource.get(
                "infrahub.attribute.name"
            ):
                attributes.append(
                    {
                        "name": resource.get("infrahub.attribute.name", ""),
                        "kind": resource.get("infrahub.attribute.kind", ""),
                        "value": None
                        if resource.get("infrahub.attribute.value") == "NULL"
                        else resource.get("infrahub.attribute.value"),
                        "value_previous": None
                        if resource.get("infrahub.attribute.value_previous") == "NULL"
                        else resource.get("infrahub.attribute.value_previous"),
                        "action": resource.get("infrahub.attribute.action", "unchanged"),
                    }
                )

        return {"attributes": attributes}

    def _return_event_specifics(self) -> dict[str, Any]:
        match self.event:
            case "infrahub.node.created" | "infrahub.node.updated" | "infrahub.node.deleted":
                return self._return_node_mutation()

        return {}

    def to_graphql(self) -> dict[str, Any]:
        response = {
            "id": str(self.id),
            "event": self.event,
            "branch": self.get_branch(),
            "account_id": self.get_account_id(),
            "occurred_at": self.occurred,
            "has_children": self.has_children(),
            "payload": self.payload,
            "level": self.get_level(),
            "primary_node": self.get_primary_node(),
            "parent_id": self.get_parent(),
            "related_nodes": self.get_related_nodes(),
        }
        response.update(self._return_event_specifics())
        return response


class PrefectEventResponse(BaseModel):
    count: int = Field(..., description="Number of matching events")
    events: list[PrefectEventData] = Field(..., description="Returned events")


class PrefectEvent:
    @classmethod
    async def query_events(
        cls,
        client: PrefectClient,
        limit: int,
        filters: EventFilter,
        offset: int | None = None,
    ) -> PrefectEventResponse:
        body = {"limit": limit, "filter": filters.model_dump(mode="json", exclude_none=True), "offset": offset}

        response = await client._client.post("/infrahub/events/filter", json=body)
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        return PrefectEventResponse(
            count=data.get("total", 0),
            events=TypeAdapter(list[PrefectEventData]).validate_python(data.get("events")),
        )

    @classmethod
    async def query(
        cls,
        fields: dict[str, Any],
        limit: int | None = None,
        offset: int | None = None,
        level: int | None = None,
        ids: list[str] | None = None,
        branch: list[str] | None = None,
        has_children: bool | None = None,
        account: list[str] | None = None,
        event_type: list[str] | None = None,
        related_node__ids: list[str] | None = None,
        primary_node__ids: list[str] | None = None,
        parent__ids: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        nodes: list[dict] = []
        limit = limit or 50

        node_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node"])
        filters = InfrahubEventFilter.from_filters(
            ids=ids,
            branch=branch,
            account=account,
            has_children=has_children,
            event_type=event_type,
            related_node__ids=related_node__ids,
            primary_node__ids=primary_node__ids,
            parent__ids=parent__ids,
            since=since,
            until=until,
            level=level,
        )

        if not node_fields:
            # This means that it's purely a count query and as such we can override the limit to avoid
            # returning data that will only be discarded
            limit = 1

        async with get_client(sync_client=False) as client:
            response = await cls.query_events(client=client, filters=filters, limit=limit, offset=offset)
            nodes = [{"node": event.to_graphql()} for event in response.events]

        return {"count": response.count, "edges": nodes}
