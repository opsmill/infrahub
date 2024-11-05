from typing import Any

from pydantic import BaseModel, Field

from infrahub.message_bus import InfrahubMessage, Meta

from .constants import EVENT_NAMESPACE


class EventMeta(BaseModel):
    request_id: str = ""
    account_id: str = ""
    initiator_id: str | None = Field(
        default=None, description="The worker identity of the initial sender of this message"
    )


class InfrahubEvent(BaseModel):
    meta: EventMeta | None = None

    def get_event_namespace(self) -> str:
        return EVENT_NAMESPACE

    def get_name(self) -> str:
        return f"{self.get_event_namespace()}.unknown"

    def get_resource(self) -> dict[str, str]:
        raise NotImplementedError

    def get_messages(self) -> list[InfrahubMessage]:
        raise NotImplementedError

    def get_related(self) -> list[dict[str, str]]:
        related: list[dict[str, str]] = []

        if not self.meta:
            return related

        if self.meta.account_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.account.{self.meta.account_id}",
                    "prefect.resource.role": "account",
                }
            )

        if self.meta.request_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.request.{self.meta.request_id}",
                    "prefect.resource.role": "request",
                }
            )

        if self.meta.initiator_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.source.{self.meta.initiator_id}",
                    "prefect.resource.role": "event_source",
                }
            )

        return related

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


class InfrahubBranchEvent(InfrahubEvent):  # pylint: disable=abstract-method
    branch: str = Field(..., description="The branch on which the event happend")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": "infrahub.branch",
                "prefect.resource.name": self.branch,
                "prefect.resource.role": "branch",
            }
        )
        return related
