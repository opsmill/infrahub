import uuid
from typing import Any

from prefect.client.orchestration import PrefectClient, get_client
from prefect.events.filters import EventFilter, EventIDFilter, EventNameFilter, EventRelatedFilter
from prefect.events.schemas.events import Event as PrefectEventModel
from prefect.events.schemas.events import ResourceSpecification
from pydantic import TypeAdapter

from infrahub.log import get_logger
from infrahub.utils import get_nested_dict

log = get_logger()


class PrefectEventData(PrefectEventModel):
    def get_branch(self) -> str | None:
        for resource in self.related:
            if resource.get("prefect.resource.id") != "infrahub.branch":
                continue
            if "prefect.resource.name" not in resource:
                continue
            return resource.get("prefect.resource.name")
        return None


class PrefectEvent:
    @classmethod
    async def query_events(cls, client: PrefectClient, filters: EventFilter | None = None) -> list[PrefectEventData]:
        body = {}
        if filters:
            body["filter"] = filters.model_dump(mode="json", exclude_unset=True)

        response = await client._client.post("/events/filter", json=body)
        response.raise_for_status()
        # TODO need to implement pagination :(
        # total_nbr_results = response.json().get("total")
        return TypeAdapter(list[PrefectEventData]).validate_python(response.json().get("events"))

    @classmethod
    def _generate_filters(
        cls,
        ids: list[str] | None = None,
        related_nodes: list[str] | None = None,
        branch: str | None = None,
    ) -> EventFilter:
        filters = EventFilter(event=EventNameFilter(prefix=["infrahub."], name=[]))  # type: ignore[call-arg]

        if ids:
            filters.id = EventIDFilter(id=[uuid.UUID(id) for id in ids])

        if branch:
            filters.related = EventRelatedFilter(  # type: ignore[call-arg]
                labels=ResourceSpecification(
                    {"prefect.resource.id": "infrahub.branch", "prefect.resource.name": branch}
                )
            )

        return filters

    @classmethod
    async def query(
        cls,
        fields: dict[str, Any],
        q: str | None = None,
        ids: list[str] | None = None,
        branch: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        nodes: list[dict] = []

        node_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node"])
        filters = cls._generate_filters(ids=ids, branch=branch)

        async with get_client(sync_client=False) as client:
            if node_fields:
                events = await cls.query_events(client=client, filters=filters)

                for event in events:
                    nodes.append(
                        {
                            "node": {
                                "id": str(event.id),
                                "event": event.event,
                                "branch": event.get_branch(),
                            }
                        }
                    )

        return {"count": len(nodes), "edges": nodes}
