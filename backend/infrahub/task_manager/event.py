import uuid
from typing import Any

from prefect.client.orchestration import PrefectClient, get_client
from prefect.events.filters import EventFilter, EventIDFilter, EventNameFilter, EventRelatedFilter, EventResourceFilter
from prefect.events.schemas.events import Event as PrefectEventModel
from prefect.events.schemas.events import ResourceSpecification
from pydantic import BaseModel, Field, TypeAdapter

from infrahub.log import get_logger
from infrahub.utils import get_nested_dict

log = get_logger()


class PrefectEventData(PrefectEventModel):
    def get_branch(self) -> str | None:
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.branch":
                continue
            if "infrahub.resource.label" not in resource:
                continue
            return resource.get("infrahub.resource.label")
        return None

    def get_account_id(self) -> str | None:
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.account":
                continue
            return resource.get("infrahub.resource.id")
        return None

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
            "occurred_at": self.occurred.to_iso8601_string(),
            "payload": self.payload,
        }
        response.update(self._return_event_specifics())
        return response


class PrefectEventResponse(BaseModel):
    count: int = Field(..., description="Number of matching events")
    events: list[PrefectEventData] = Field(..., description="Returned events")


class PrefectEvent:
    @classmethod
    async def query_events(
        cls, client: PrefectClient, filters: EventFilter | None = None, limit: int | None = None
    ) -> PrefectEventResponse:
        body: dict[str, Any] = {}
        if filters:
            body["filter"] = filters.model_dump(mode="json", exclude_unset=True)

        if limit is not None:
            body["limit"] = limit

        response = await client._client.post("/events/filter", json=body)
        response.raise_for_status()
        # TODO need to implement pagination :(
        return PrefectEventResponse(
            count=response.json().get("total", 0),
            events=TypeAdapter(list[PrefectEventData]).validate_python(response.json().get("events")),
        )

    @classmethod
    def _generate_filters(
        cls,
        ids: list[str] | None = None,
        account: str | None = None,
        related_node__ids: list[str] | None = None,
        branch: str | None = None,
    ) -> EventFilter:
        filters = EventFilter(event=EventNameFilter(prefix=["infrahub."], name=[]))

        if ids:
            filters.id = EventIDFilter(id=[uuid.UUID(id) for id in ids])

        if related_node__ids:
            filters.resource = EventResourceFilter(
                labels=ResourceSpecification({"infrahub.node.id": related_node__ids})
            )

        if branch:
            filters.related = EventRelatedFilter(
                labels=ResourceSpecification(
                    {"prefect.resource.role": "infrahub.branch", "infrahub.resource.label": branch}
                )
            )

        if account:
            filters.related = EventRelatedFilter(
                labels=ResourceSpecification(
                    {"prefect.resource.role": "infrahub.account", "infrahub.resource.id": account}
                )
            )

        return filters

    @classmethod
    async def query(
        cls,
        fields: dict[str, Any],
        q: str | None = None,  # noqa: ARG003
        ids: list[str] | None = None,
        branch: str | None = None,
        account: str | None = None,
        limit: int | None = None,
        related_node__ids: list[str] | None = None,
        offset: int | None = None,  # noqa: ARG003
    ) -> dict[str, Any]:
        nodes: list[dict] = []

        node_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node"])
        filters = cls._generate_filters(ids=ids, branch=branch, account=account, related_node__ids=related_node__ids)

        if not node_fields:
            # This means that it's purely a count query and as such we can override the limit to avoid
            # returning data that will only be discarded
            limit = 1

        async with get_client(sync_client=False) as client:
            response = await cls.query_events(client=client, filters=filters, limit=limit)
            nodes = [{"node": event.to_graphql()} for event in response.events]

        return {"count": response.count, "edges": nodes}
