from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from infrahub.message_bus import InfrahubMessage, Meta

from .constants import EVENT_NAMESPACE


class EventMeta(BaseModel):
    branch: str = ""
    request_id: str = ""
    account_id: str = ""
    initiator_id: str | None = Field(
        default=None, description="The worker identity of the initial sender of this message"
    )
    context: list[dict] = Field(default_factory=list)

    def get_related(self) -> list[dict[str, str]]:
        related: list[dict[str, str]] = []
        if self.account_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.account.{self.account_id}",
                    "infrahub.resource.id": self.account_id,
                    "prefect.resource.role": "account",
                }
            )

        if self.branch:
            related.append(
                {
                    "prefect.resource.id": "infrahub.branch",
                    "prefect.resource.name": self.branch,
                    "prefect.resource.role": "branch",
                }
            )

        return related


class InfrahubEvent(BaseModel):
    meta: EventMeta | None = None

    id: UUID = Field(
        default_factory=uuid4,
        description="UUID of the event",
    )

    event_name: str

    def get_id(self) -> str:
        return str(self.id)

    def get_event_namespace(self) -> str:
        return EVENT_NAMESPACE

    def get_name(self) -> str:
        return self.event_name

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
        if not self.meta:
            return meta

        if self.meta.initiator_id:
            meta.initiator_id = self.meta.initiator_id
        if self.meta.request_id:
            meta.initiator_id = self.meta.request_id

        return meta
