from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, TypedDict

from prefect.client.orchestration import PrefectClient, get_client
from prefect.events.schemas.events import Event as PrefectEventModel
from pydantic import BaseModel, Field, TypeAdapter

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.diff.payload_builder import get_display_labels_per_kind
from infrahub.core.query.node import NodeGetKindQuery
from infrahub.core.registry import registry
from infrahub.exceptions import BranchNotFoundError, ServiceUnavailableError
from infrahub.log import get_logger
from infrahub.utils import get_nested_dict

log = get_logger()

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

    from .models import InfrahubEventFilter


class EventNode(TypedDict):
    id: str
    kind: str
    display_label: str | None


class PrefectEventData(PrefectEventModel):
    def get_branch(self) -> str | None:
        for resource in self.related:
            if resource.role != "infrahub.branch":
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

    def get_primary_node(
        self, branch_name: str | None = None, label_mapper: DisplayLabelMapper | None = None
    ) -> EventNode | None:
        node_id = self.resource.get("infrahub.node.id")
        node_kind = self.resource.get("infrahub.node.kind")
        if node_id and node_kind:
            return {
                "id": node_id,
                "kind": node_kind,
                "display_label": label_mapper.get_node_label(branch_name=branch_name, node_id=node_id)
                if label_mapper
                else None,
            }

        return None

    def get_related_nodes(
        self, branch_name: str | None = None, label_mapper: DisplayLabelMapper | None = None
    ) -> list[EventNode]:
        related_nodes: list[EventNode] = []
        for resource in self.related:
            if resource.role != "infrahub.related.node":
                continue

            node_id = resource.get("prefect.resource.id")
            node_kind = resource.get("infrahub.node.kind")
            if node_id == self.resource.get("infrahub.node.id"):
                # Don't include the primary node as a related node.
                continue
            if node_id and node_kind:
                related_nodes.append(
                    {
                        "id": node_id,
                        "kind": node_kind,
                        "display_label": label_mapper.get_node_label(branch_name=branch_name, node_id=node_id)
                        if label_mapper
                        else None,
                    }
                )

        return related_nodes

    def get_account_id(self) -> str | None:
        for resource in self.related:
            if resource.role != "infrahub.account":
                continue
            return resource.get("infrahub.resource.id")
        return None

    def has_children(self) -> bool:
        for resource in self.related:
            if resource.role != "infrahub.event":
                continue
            if resource.get("infrahub.event.has_children") == "true":
                return True
            return False
        return False

    def _return_node_mutation(self) -> dict[str, Any]:
        attributes = []

        for resource in self.related:
            if resource.role == "infrahub.node.field_update" and resource.get("infrahub.attribute.name"):
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

    def _return_group_event(self, branch_name: str | None, label_mapper: DisplayLabelMapper) -> dict[str, Any]:
        members = []
        ancestors = []

        for resource in self.related:
            if resource.role == "infrahub.group.member" and resource.get("infrahub.node.kind"):
                members.append(
                    {
                        "id": resource.id,
                        "kind": resource.get("infrahub.node.kind"),
                        "display_label": label_mapper.get_node_label(branch_name=branch_name, node_id=resource.id),
                    }
                )
            elif resource.role == "infrahub.group.ancestor" and resource.get("infrahub.node.kind"):
                ancestors.append(
                    {
                        "id": resource.id,
                        "kind": resource.get("infrahub.node.kind"),
                        "display_label": label_mapper.get_node_label(branch_name=branch_name, node_id=resource.id),
                    }
                )

        return {"members": members, "ancestors": ancestors}

    def _return_event_specifics(self, branch_name: str | None, label_mapper: DisplayLabelMapper) -> dict[str, Any]:
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
                event_specifics = self._return_group_event(branch_name=branch_name, label_mapper=label_mapper)

        return event_specifics

    def to_graphql(self, label_mapper: DisplayLabelMapper) -> dict[str, Any]:
        branch_name = self.get_branch()
        response = {
            "id": str(self.id),
            "event": self.event,
            "branch": branch_name,
            "account_id": self.get_account_id(),
            "account": label_mapper.get_account(account_id=self.get_account_id()),
            "occurred_at": self.occurred,
            "has_children": self.has_children(),
            "payload": self.payload,
            "level": self.get_level(),
            "primary_node": self.get_primary_node(branch_name=branch_name, label_mapper=label_mapper),
            "parent_id": self.get_parent(),
            "related_nodes": self.get_related_nodes(branch_name=branch_name, label_mapper=label_mapper),
        }
        response.update(self._return_event_specifics(branch_name=branch_name, label_mapper=label_mapper))
        return response


class DisplayLabelMapper:
    def __init__(self, db: InfrahubDatabase, events: list[PrefectEventData]) -> None:
        self._db = db
        self._events = events
        self._display_labels: dict[str, dict[str, str]] = {}
        self._account_labels: dict[str, EventNode] = {}

    @property
    def account_labels(self) -> dict[str, EventNode]:
        return self._account_labels

    @property
    def display_labels(self) -> dict[str, dict[str, str]]:
        return self._display_labels

    def get_account(self, account_id: str | None) -> EventNode | None:
        if not account_id:
            return None
        if account_id in self.account_labels:
            return self.account_labels[account_id]

        return {"id": account_id, "kind": "CoreGenericAccount", "display_label": None}

    def get_node_label(self, branch_name: str | None, node_id: str | None) -> str | None:
        branch_name = branch_name or registry.default_branch
        if branch_name not in self._display_labels or not node_id:
            return None

        return self._display_labels[branch_name].get(node_id)

    async def populate_display_labels(self) -> None:
        await self._populate_account_labels()
        await self._populate_node_labels()

    async def _populate_account_labels(self) -> None:
        account_ids = set()
        for event in self._events:
            if account_id := event.get_account_id():
                account_ids.add(account_id)

        query = await NodeGetKindQuery.init(db=self._db, ids=list(account_ids))
        await query.execute(db=self._db)
        node_kind_map = query.get_id_by_kind()
        for kind, accounts in node_kind_map.items():
            account_labels = await get_display_labels_per_kind(
                kind=kind, branch_name=registry.default_branch, ids=list(accounts), db=self._db
            )
            for account_id, display_label in account_labels.items():
                self._account_labels[account_id] = {"display_label": display_label, "id": account_id, "kind": kind}

    async def _populate_node_labels(self) -> None:
        node_ids_by_branch_and_kind: dict[str, dict[str, set[str]]] = {}
        for event in self._events:
            branch = event.get_branch() or registry.default_branch
            if branch not in node_ids_by_branch_and_kind:
                node_ids_by_branch_and_kind[branch] = {}
            observed_nodes = event.get_related_nodes()
            if primary := event.get_primary_node():
                observed_nodes.append(primary)
            for observed_node in observed_nodes:
                if observed_node["kind"] not in node_ids_by_branch_and_kind[branch]:
                    node_ids_by_branch_and_kind[branch][observed_node["kind"]] = set()
                node_ids_by_branch_and_kind[branch][observed_node["kind"]].add(observed_node["id"])

        for branch, ids_by_kind in node_ids_by_branch_and_kind.items():
            for kind, ids in ids_by_kind.items():
                try:
                    labels = await get_display_labels_per_kind(
                        kind=kind, ids=list(ids), branch_name=branch, db=self._db, skip_missing_schema=True
                    )
                except BranchNotFoundError:
                    # Ignore display labels for branches that have been deleted
                    continue
                if branch not in self._display_labels:
                    self._display_labels[branch] = {}
                self._display_labels[branch].update(labels)


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
            response = await client._client.post("/infrahub/events/filter", json=body)
            if response.status_code == 200:
                break
            await asyncio.sleep(0.1)

        if response.status_code != 200:
            raise ServiceUnavailableError(
                message=f"Unable to query prefect due to invalid response from the server (status_code={response.status_code})"
            )
        data: dict[str, Any] = response.json()

        return PrefectEventResponse(
            count=data.get("total", 0),
            events=TypeAdapter(list[PrefectEventData]).validate_python(data.get("events")),
        )

    @classmethod
    async def query(
        cls,
        db: InfrahubDatabase,
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

        label_mapper = DisplayLabelMapper(db=db, events=response.events)
        await label_mapper.populate_display_labels()

        nodes = [{"node": event.to_graphql(label_mapper=label_mapper)} for event in response.events]

        return {"count": response.count, "edges": nodes}
