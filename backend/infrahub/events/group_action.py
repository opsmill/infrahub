from typing import ClassVar
from uuid import UUID

from pydantic import Field

from infrahub.core.constants import InfrahubKind, MutationAction
from infrahub.external_protocols import ExternalAuthProtocol

from .constants import EVENT_NAMESPACE
from .models import EventNode, InfrahubEvent


class GroupMutatedEvent(InfrahubEvent):
    """Event generated when a node has been mutated."""

    kind: str = Field(..., description="The type of updated group")
    node_id: str = Field(..., description="The ID of the updated group")
    action: MutationAction = Field(..., description="The action taken on the node")
    members: list[EventNode] = Field(default_factory=list, description="Updated members during this event.")
    ancestors: list[EventNode] = Field(
        default_factory=list, description="A list of groups that are ancestors of this group."
    )

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()

        if self.kind in [InfrahubKind.GENERATORGROUP, InfrahubKind.GENERATORAWAREGROUP, InfrahubKind.GRAPHQLQUERYGROUP]:
            # Temporary workaround to avoid too large payloads for the related field
            return related

        related.append(
            {
                "prefect.resource.id": self.node_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": self.kind,
            }
        )
        related.append(
            {
                "prefect.resource.id": self.node_id,
                "prefect.resource.role": "infrahub.group.update",
                "infrahub.node.kind": self.kind,
            }
        )

        for member in self.members:
            related.append(
                {
                    "prefect.resource.id": member.id,
                    "prefect.resource.role": "infrahub.group.member",
                    "infrahub.node.kind": member.kind,
                }
            )
            related.append(
                {
                    "prefect.resource.id": member.id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": member.kind,
                }
            )

        for ancestor in self.ancestors:
            related.append(
                {
                    "prefect.resource.id": ancestor.id,
                    "prefect.resource.role": "infrahub.group.ancestor",
                    "infrahub.node.kind": ancestor.kind,
                }
            )
            related.append(
                {
                    "prefect.resource.id": ancestor.id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": ancestor.kind,
                }
            )
            related.append(
                {
                    "prefect.resource.id": ancestor.id,
                    "prefect.resource.role": "infrahub.group.update",
                    "infrahub.node.kind": ancestor.kind,
                }
            )

        return related

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.node.{self.node_id}",
            "infrahub.node.kind": self.kind,
            "infrahub.node.id": self.node_id,
            "infrahub.node.action": self.action.value,
            "infrahub.node.root_id": self.node_id,
            "infrahub.branch.name": self.meta.context.branch.name,
        }


class GroupMemberAddedEvent(GroupMutatedEvent):
    """Event generated when a one or more members have been added to a group."""

    action: MutationAction = MutationAction.CREATED
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.member_added"
    infrahub_node_kind_event: ClassVar[bool] = True


class GroupMemberRemovedEvent(GroupMutatedEvent):
    """Event generated when a one or more members have been removed to a group."""

    action: MutationAction = MutationAction.DELETED
    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.member_removed"
    infrahub_node_kind_event: ClassVar[bool] = True


class GroupAutoCreateEvent(InfrahubEvent):
    """Concrete base for events emitted by the auto-create-group flow during a login."""

    idp: str = Field(..., description="Configured name of the originating identity provider")
    triggering_user_id: UUID = Field(..., description="The account whose login produced the event")
    triggering_user_name: str = Field(..., description="Login identifier of the triggering account")
    protocol: ExternalAuthProtocol = Field(..., description="Authentication protocol used for the login")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.account.{self.triggering_user_id}",
            "infrahub.account.account_id": str(self.triggering_user_id),
            "infrahub.account.account_name": self.triggering_user_name,
            "infrahub.security.idp": self.idp,
            "infrahub.security.protocol": self.protocol.value,
            "infrahub.branch.name": self.meta.context.branch.name,
        }


class GroupAutoCreatedEvent(GroupAutoCreateEvent):
    """Emitted exactly once per successful auto-creation of a new `CoreAccountGroup`."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.auto_created"

    group_id: UUID = Field(..., description="UUID of the newly created group")
    group_name: str = Field(..., description="Local name of the new group")
    source_pattern: str = Field(..., description="Raw regex pattern from the configured filter that matched")
    origin_value: str = Field(..., description="Configured provider name written to the group's origin attribute")

    def get_resource(self) -> dict[str, str]:
        resource = super().get_resource()
        resource["infrahub.node.id"] = str(self.group_id)
        resource["infrahub.node.kind"] = InfrahubKind.ACCOUNTGROUP
        resource["infrahub.group.name"] = self.group_name
        resource["infrahub.security.source_pattern"] = self.source_pattern
        resource["infrahub.security.origin_value"] = self.origin_value
        return resource

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": str(self.group_id),
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": InfrahubKind.ACCOUNTGROUP,
            }
        )
        return related


class GroupAutoCreateRejectedEvent(GroupAutoCreateEvent):
    """Emitted when a matched claim's effective name fails identifier validation."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.auto_create_rejected"

    rejected_claim_value: str = Field(..., description="Verbatim, length-truncated rejected claim value")

    def get_resource(self) -> dict[str, str]:
        resource = super().get_resource()
        resource["infrahub.security.rejected_claim_value"] = self.rejected_claim_value
        return resource


class GroupAutoCreateCappedEvent(GroupAutoCreateEvent):
    """Emitted at most once per login when the per-login cap on new-group creation is reached."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.group.auto_create_capped"

    cap_value: int = Field(..., description="Configured per-login cap value")
    dropped_claims: list[str] = Field(..., description="Verbatim, per-entry length-truncated dropped claims")
    dropped_count: int = Field(..., description="Total count of dropped claims for this login")

    def get_resource(self) -> dict[str, str]:
        resource = super().get_resource()
        resource["infrahub.security.cap_value"] = str(self.cap_value)
        resource["infrahub.security.dropped_count"] = str(self.dropped_count)
        return resource

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        for idx, claim in enumerate(self.dropped_claims):
            related.append(
                {
                    "prefect.resource.id": f"infrahub.security.dropped_claim.{idx}",
                    "prefect.resource.role": "infrahub.security.dropped_claim",
                    "infrahub.security.dropped_claim.value": claim,
                }
            )
        return related
