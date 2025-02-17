from __future__ import annotations

from typing import Any, cast, final
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from infrahub import __version__
from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext  # noqa: TC001
from infrahub.core.branch import Branch  # noqa: TC001
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
    context: InfrahubContext = Field(..., description="The context used when originating this event")
    level: int = Field(default=0)
    has_children: bool = Field(
        default=False, description="Indicates if this event might potentially have child events under it."
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="UUID of the event",
    )

    parent: UUID | None = Field(default=None, description="The UUID of the parent event if applicable")

    def get_id(self) -> str:
        return str(self.id)

    def get_related(self) -> list[dict[str, str]]:
        related: list[dict[str, str]] = [
            {"prefect.resource.id": __version__, "prefect.resource.role": "infrahub.version"},
            {
                "prefect.resource.id": self.get_id(),
                "prefect.resource.role": "infrahub.event",
                "infrahub.event.has_children": str(self.has_children).lower(),
            },
        ]
        if self.account_id:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.account.{self.account_id}",
                    "prefect.resource.role": "infrahub.account",
                    "infrahub.resource.id": self.account_id,
                }
            )

        if self.branch:
            related.append(
                {
                    "prefect.resource.id": f"infrahub.branch.{self.branch.get_uuid()}",
                    "prefect.resource.role": "infrahub.branch",
                    "infrahub.resource.id": str(self.branch.get_uuid()),
                    "infrahub.resource.label": self.branch.name,
                }
            )

        if self.parent:
            related.append(
                {
                    "prefect.resource.id": self.get_id(),
                    "prefect.resource.role": "infrahub.child_event",
                    "infrahub.event_parent.id": str(self.parent),
                }
            )

        return related

    @classmethod
    def with_dummy_context(cls, branch: Branch) -> EventMeta:
        return cls(
            branch=branch,
            context=InfrahubContext.init(
                branch=branch, account=AccountSession(auth_type=AuthType.NONE, authenticated=False, account_id="")
            ),
        )

    @classmethod
    def from_parent(cls, parent: InfrahubEvent) -> EventMeta:
        """Create the metadata from an existing event

        Note that this action will modify the existing event to indicate that children might be attached to the event
        """
        parent.meta.has_children = True
        return cls(
            parent=parent.meta.id,
            branch=parent.meta.branch,
            request_id=parent.meta.request_id,
            initiator_id=parent.meta.initiator_id,
            account_id=parent.meta.account_id,
            level=parent.meta.level + 1,
            context=parent.meta.context,
        )


class InfrahubEvent(BaseModel):
    meta: EventMeta = Field(..., description="Metadata for the event")

    def get_id(self) -> str:
        return self.meta.get_id()

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
        """The purpose if this method is to allow subclasses to define their own payload.

        It should not be used to get the complete payload instead .get_event_payload() should
        be used for that as it will always contain the 'context' key regardless of changes
        in child classes
        """
        return {}

    @final
    def get_event_payload(self) -> dict[str, Any]:
        """This method should be used when emitting the event to the event broker"""
        event_payload = self.get_payload()
        event_payload["context"] = self.meta.context.model_dump(mode="json")
        return event_payload

    def get_message_meta(self) -> Meta:
        meta = Meta()

        meta.initiator_id = self.meta.initiator_id
        if self.meta.request_id:
            meta.initiator_id = self.meta.request_id

        return meta

    @computed_field
    def event_name(self) -> str:
        raise NotImplementedError("The event name has not been defined")
