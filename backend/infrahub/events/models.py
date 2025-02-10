from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from infrahub import __version__
from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.constants import EventLevel
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.worker import WORKER_IDENTITY

from .constants import EVENT_NAMESPACE


class EventNode(BaseModel):
    id: str
    kind: str


class EventMeta(BaseModel):
    branch: Branch | None = Field(default=None)
    request_id: str = ""
    account_id: str | None = Field(default=None, description="The ID of the account triggering this event")
    initiator_id: str = Field(
        default=WORKER_IDENTITY, description="The worker identity of the initial sender of this message"
    )
    context: list[dict] = Field(default_factory=list)
    level: EventLevel = Field(default=EventLevel.ZERO)

    def get_related(self) -> list[dict[str, str]]:
        related: list[dict[str, str]] = []
        event_resource = {"infrahub.event.level": self.level.value}
        if self.account_id:
            event_resource["infrahub.account.id"] = self.account_id
            related.append(
                {
                    "prefect.resource.id": f"infrahub.account.{self.account_id}",
                    "prefect.resource.role": "infrahub.account",
                    "infrahub.resource.id": self.account_id,
                }
            )

        if self.branch:
            event_resource["infrahub.branch.label"] = self.branch.name
            related.append(
                {
                    "prefect.resource.id": f"infrahub.branch.{self.branch.get_uuid()}",
                    "prefect.resource.role": "infrahub.branch",
                    "infrahub.resource.id": str(self.branch.get_uuid()),
                    "infrahub.resource.label": self.branch.name,
                }
            )

        # This is currently required to let us filter events with the InfrahubEvent query when matching
        # against multiple components such as both branch and account
        event_resource["prefect.resource.id"] = str(uuid4())
        event_resource["prefect.resource.role"] = "infrahub.eventlog"
        related.append(event_resource)

        related.append({"prefect.resource.id": __version__, "prefect.resource.role": "infrahub.version"})

        return related

    @classmethod
    def default(cls) -> EventMeta:
        return cls()


class InfrahubEvent(BaseModel):
    meta: EventMeta = Field(default_factory=EventMeta.default)

    id: UUID = Field(
        default_factory=uuid4,
        description="UUID of the event",
    )

    def get_id(self) -> str:
        return str(self.id)

    def get_event_namespace(self) -> str:
        return EVENT_NAMESPACE

    def get_name(self) -> str:
        # Convince linters that @computed_field is a property and not a method...
        return cast(str, self.event_name)

    def get_resource(self) -> dict[str, str]:
        raise NotImplementedError

    def get_messages(self) -> list[InfrahubMessage]:
        raise NotImplementedError

    def get_related(self) -> list[dict[str, str]]:
        if not self.meta:
            return []
        return self.meta.get_related()

    def get_payload(self) -> dict[str, Any]:
        return {}

    def get_message_meta(self) -> Meta:
        meta = Meta()

        meta.initiator_id = self.meta.initiator_id
        if self.meta.request_id:
            meta.initiator_id = self.meta.request_id

        return meta

    @computed_field
    def event_name(self) -> str:
        raise NotImplementedError("The event name has not been defined")
