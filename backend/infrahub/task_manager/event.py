from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from prefect.client.orchestration import PrefectClient, get_client
from prefect.events.schemas.events import Event as PrefectEventModel
from prefect.exceptions import PrefectHTTPStatusError
from pydantic import BaseModel, Field, TypeAdapter

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.exceptions import ServiceUnavailableError
from infrahub.log import get_logger
from infrahub.utils import get_nested_dict

log = get_logger()

if TYPE_CHECKING:
    from .models import InfrahubEventFilter


class PrefectEventData(PrefectEventModel):
    def get_branch(self) -> str | None:
        for resource in self.related:
            if resource.get("prefect.resource.role") != "infrahub.branch":
                continue
            if "infrahub.resource.label" not in resource:
                continue
            if resource.get("infrahub.resource.label") == GLOBAL_BRANCH_NAME:
                return None
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
        relationships = []

        for resource in self.related:
            if resource.role == "infrahub.node.attribute_update" and resource.get("infrahub.attribute.name"):
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
            elif resource.role == "infrahub.node.relationship_update":
                relationships.append(
                    {
                        "name": resource.get("infrahub.relationship.name"),
                        "action": resource.get("infrahub.relationship.peer_status"),
                        "peer": {
                            "id": resource.get("infrahub.relationship.peer_id"),
                            "kind": resource.get("infrahub.relationship.peer_kind"),
                        },
                    }
                )

        return {"attributes": attributes, "relationships": relationships}

    def _get_branch_name_from_resource(self) -> str:
        return self.resource.get("infrahub.branch.name") or ""

    def _return_artifact_event(self) -> dict[str, Any]:
        checksum = ""
        checksum_previous: str | None = None
        storage_id = ""
        storage_id_previous: str | None = None
        artifact_definition_id = ""
        for resource in self.related:
            if resource.role == "infrahub.artifact":
                checksum = resource.get("infrahub.artifact.checksum") or ""
                checksum_previous = resource.get("infrahub.artifact.checksum_previous")
                storage_id = resource.get("infrahub.artifact.storage_id") or ""
                storage_id_previous = resource.get("infrahub.artifact.storage_id_previous")
                artifact_definition_id = resource.get("infrahub.artifact.artifact_definition_id") or ""

        return {
            "checksum": checksum,
            "checksum_previous": checksum_previous,
            "storage_id": storage_id,
            "storage_id_previous": storage_id_previous,
            "artifact_definition_id": artifact_definition_id,
        }

    def _return_branch_created(self) -> dict[str, Any]:
        return {"created_branch": self._get_branch_name_from_resource()}

    def _return_branch_deleted(self) -> dict[str, Any]:
        return {"deleted_branch": self._get_branch_name_from_resource()}

    def _return_branch_merged(self) -> dict[str, Any]:
        return {"source_branch": self._get_branch_name_from_resource()}

    def _return_branch_rebased(self) -> dict[str, Any]:
        return {"rebased_branch": self._get_branch_name_from_resource()}

    def _return_group_event(self) -> dict[str, Any]:
        members = []
        ancestors = []

        for resource in self.related:
            if resource.role == "infrahub.group.member" and resource.get("infrahub.node.kind"):
                members.append({"id": resource.id, "kind": resource.get("infrahub.node.kind")})
            elif resource.role == "infrahub.group.ancestor" and resource.get("infrahub.node.kind"):
                ancestors.append({"id": resource.id, "kind": resource.get("infrahub.node.kind")})

        return {"members": members, "ancestors": ancestors}

    def _return_event_specifics(self) -> dict[str, Any]:
        """Return event specific data based on the type of event being processed"""

        event_specifics = {}

        match self.event:
            case "infrahub.artifact.created" | "infrahub.artifact.updated":
                event_specifics = self._return_artifact_event()
            case "infrahub.node.created" | "infrahub.node.updated" | "infrahub.node.deleted":
                event_specifics = self._return_node_mutation()
            case "infrahub.branch.created":
                event_specifics = self._return_branch_created()
            case "infrahub.branch.deleted":
                event_specifics = self._return_branch_deleted()
            case "infrahub.branch.merged":
                event_specifics = self._return_branch_merged()
            case "infrahub.branch.rebased":
                event_specifics = self._return_branch_rebased()
            case "infrahub.group.member_added" | "infrahub.group.member_removed":
                event_specifics = self._return_group_event()

        return event_specifics

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
        filters: InfrahubEventFilter,
        offset: int | None = None,
    ) -> PrefectEventResponse:
        body = {"limit": limit, "filter": filters.model_dump(mode="json", exclude_none=True), "offset": offset}

        # Retry due to https://github.com/PrefectHQ/prefect/issues/16299
        for _ in range(1, 5):
            prefect_error: PrefectHTTPStatusError | None = None
            try:
                response = await client._client.post("/infrahub/events/filter", json=body)
                break
            except PrefectHTTPStatusError as exc:
                prefect_error = exc
                await asyncio.sleep(0.1)

        if prefect_error:
            raise ServiceUnavailableError(
                message=f"Unable to query prefect due to invalid response from the server (status_code={prefect_error.response.status_code})"
            )
        data: dict[str, Any] = response.json()

        return PrefectEventResponse(
            count=data.get("total", 0),
            events=TypeAdapter(list[PrefectEventData]).validate_python(data.get("events")),
        )

    @classmethod
    async def query(
        cls,
        fields: dict[str, Any],
        event_filter: InfrahubEventFilter,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        nodes: list[dict] = []
        limit = limit or 50

        node_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node"])

        if not node_fields:
            # This means that it's purely a count query and as such we can override the limit to avoid
            # returning data that will only be discarded
            limit = 1

        async with get_client(sync_client=False) as client:
            response = await cls.query_events(client=client, filters=event_filter, limit=limit, offset=offset)
            nodes = [{"node": event.to_graphql()} for event in response.events]

        return {"count": response.count, "edges": nodes}
