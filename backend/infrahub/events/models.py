from __future__ import annotations

from copy import deepcopy
from typing import Any, ClassVar, Self, final
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from infrahub import __version__
from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.worker import WORKER_IDENTITY

from .constants import EVENT_NAMESPACE


class EventNode(BaseModel):
    id: str
    kind: str


class ParentEvent(BaseModel):
    id: str
    name: str


class EventMeta(BaseModel):
    branch: Branch | None = Field(default=None, description="The branch on which originate this event")
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
    ancestors: list[ParentEvent] = Field(default_factory=list, description="Any event used to trigger this event")
    _created_with_context: bool = PrivateAttr(default=False)

    def get_branch_id(self) -> str:
        if self.context.branch.id:
            return self.context.branch.id

        if self.branch:
            return str(self.branch.get_uuid())

        return ""

    def get_id(self) -> str:
        return str(self.id)

    def get_related(self) -> list[dict[str, str]]:
        related: list[dict[str, str]] = [
            {"prefect.resource.id": __version__, "prefect.resource.role": "infrahub.version"},
            {
                "prefect.resource.id": self.get_id(),
                "prefect.resource.role": "infrahub.event",
                "infrahub.event.has_children": str(self.has_children).lower(),
                "infrahub.event.level": str(self.level),
            },
            {
                "prefect.resource.id": f"infrahub.account.{self.context.account.account_id}",
                "prefect.resource.role": "infrahub.account",
                "infrahub.resource.id": self.context.account.account_id,
            },
            {
                "prefect.resource.id": f"infrahub.branch.{self.get_branch_id()}",
                "prefect.resource.role": "infrahub.branch",
                "infrahub.resource.id": self.get_branch_id(),
                "infrahub.resource.label": self.context.branch.name,
            },
        ]

        if self.parent:
            related.append(
                {
                    "prefect.resource.id": self.get_id(),
                    "prefect.resource.role": "infrahub.child_event",
                    "infrahub.event_parent.id": str(self.parent),
                }
            )

        for ancestor in self.ancestors:
            related.append(
                {
                    "prefect.resource.id": ancestor.id,
                    "prefect.resource.role": "infrahub.ancestor_event",
                    "infrahub.ancestor_event.name": ancestor.name,
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
    def from_parent(cls, parent: InfrahubEvent, branch: Branch | None = None) -> EventMeta:
        """Create the metadata from an existing event

        Note that this action will modify the existing event to indicate that children might be attached to the event
        """
        parent.meta.has_children = True
        context = deepcopy(parent.meta.context)
        if branch:
            context.branch.name = branch.name
            context.branch.id = str(branch.get_uuid())

        return cls(
            parent=parent.meta.id,
            branch=parent.meta.branch,
            request_id=parent.meta.request_id,
            initiator_id=parent.meta.initiator_id,
            account_id=parent.meta.account_id,
            level=parent.meta.level + 1,
            context=context,
            ancestors=[ParentEvent(id=parent.get_id(), name=parent.event_name)] + parent.meta.ancestors,
        )

    @classmethod
    def from_context(cls, context: InfrahubContext, branch: Branch | None = None) -> EventMeta:
        # Create a copy of the context so local changes aren't brought back to a parent object
        meta = cls(context=deepcopy(context))
        meta._created_with_context = True
        if branch:
            meta.context.branch.name = branch.name
            meta.context.branch.id = str(branch.get_uuid())
        return meta


class InfrahubEvent(BaseModel):
    meta: EventMeta = Field(..., description="Metadata for the event")

    event_name: ClassVar[str] = Field(..., description="The name of the event")
    infrahub_node_kind_event: ClassVar[bool] = False

    def get_id(self) -> str:
        return self.meta.get_id()

    def get_event_namespace(self) -> str:
        return EVENT_NAMESPACE

    def get_resource(self) -> dict[str, str]:
        raise NotImplementedError

    def get_messages(self) -> list[InfrahubMessage]:
        return []

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
        return self.model_dump(exclude={"meta"})

    @final
    def get_event_payload(self) -> dict[str, Any]:
        """This method should be used when emitting the event to the event broker"""
        event_payload = {"data": self.get_payload(), "context": self.meta.context.to_event()}
        return event_payload

    def get_message_meta(self) -> Meta:
        meta = Meta()

        meta.initiator_id = self.meta.initiator_id
        if self.meta.request_id:
            meta.initiator_id = self.meta.request_id

        return meta

    @model_validator(mode="after")
    def update_context(self) -> Self:
        """Update the context object using this event provided that the meta data was created with a context."""
        if self.meta._created_with_context:
            self.meta.context.set_event(self.event_name, id=self.get_id())
        return self
