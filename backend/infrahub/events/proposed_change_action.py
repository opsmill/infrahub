from typing import ClassVar

from pydantic import Field

from infrahub.core.constants import InfrahubKind, MutationAction

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class ProposedChangeEvent(InfrahubEvent):
    proposed_change_id: str = Field(..., description="The ID of the proposed change")
    proposed_change_name: str = Field(..., description="The name of the proposed change")
    proposed_change_state: str = Field(..., description="The state of the proposed change")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.proposed_change.{self.proposed_change_id}",
            "infrahub.node.kind": InfrahubKind.PROPOSEDCHANGE,
            "infrahub.node.id": self.proposed_change_id,
            "infrahub.proposed_change.name": self.proposed_change_name,
            "infrahub.proposed_change.state": self.proposed_change_state,
            "infrahub.branch.name": self.meta.context.branch.name,
        }


class ProposedChangeReviewEvent(ProposedChangeEvent):
    reviewer_account_id: str = Field(..., description="The ID of the user who reviewed the proposed change")
    reviewer_account_name: str = Field(..., description="The name of the user who reviewed the proposed change")
    reviewer_decision: str = Field(..., description="The decision made by the reviewer")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.reviewer_account_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": InfrahubKind.GENERICACCOUNT,
                "infrahub.node.id": self.reviewer_account_id,
                "infrahub.reviewer.account.name": self.reviewer_account_name,
            }
        )
        return related

    def get_resource(self) -> dict[str, str]:
        return {**super().get_resource(), "infrahub.proposed_change.reviewer_decision": self.reviewer_decision}


class ProposedChangeReviewRevokedEvent(ProposedChangeEvent):
    reviewer_account_id: str = Field(..., description="The ID of the user who reviewed the proposed change")
    reviewer_account_name: str = Field(..., description="The name of the user who reviewed the proposed change")
    reviewer_former_decision: str = Field(..., description="The former decision made by the reviewer")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.reviewer_account_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": InfrahubKind.GENERICACCOUNT,
                "infrahub.node.id": self.reviewer_account_id,
                "infrahub.reviewer.account.name": self.reviewer_account_name,
            }
        )
        return related

    def get_resource(self) -> dict[str, str]:
        return {
            **super().get_resource(),
            "infrahub.proposed_change.reviewer_former_decision": self.reviewer_former_decision,
        }


class ProposedChangeMergedEvent(ProposedChangeEvent):
    """Event generated when a proposed change has been merged"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.merged"

    merged_by_account_id: str = Field(..., description="The ID of the user who merged the proposed change")
    merged_by_account_name: str = Field(..., description="The name of the user who merged the proposed change")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.merged_by_account_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": InfrahubKind.GENERICACCOUNT,
                "infrahub.node.id": self.merged_by_account_id,
                "infrahub.merged_by.account.name": self.merged_by_account_name,
            }
        )
        return related

    def get_resource(self) -> dict[str, str]:
        return {
            **super().get_resource(),
            "infrahub.proposed_change.merged_by_account_id": self.merged_by_account_id,
            "infrahub.proposed_change.merged_by_account_name": self.merged_by_account_name,
        }


class ProposedChangeReviewRequestedEvent(ProposedChangeEvent):
    """Event generated when a proposed change has been flagged for review"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.review_requested"

    requested_by_account_id: str = Field(
        ..., description="The ID of the user who requested the proposed change to be reviewed"
    )
    requested_by_account_name: str = Field(
        ..., description="The name of the user who requested the proposed change to be reviewed"
    )

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.requested_by_account_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": InfrahubKind.GENERICACCOUNT,
                "infrahub.node.id": self.requested_by_account_id,
                "infrahub.requested_by.account.name": self.requested_by_account_name,
            }
        )
        return related


class ProposedChangeApprovedEvent(ProposedChangeReviewEvent):
    """Event generated when a proposed change has been approved"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.approved"


class ProposedChangeRejectedEvent(ProposedChangeReviewEvent):
    """Event generated when a proposed change has been rejected"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.rejected"


class ProposedChangeApprovalRevokedEvent(ProposedChangeReviewRevokedEvent):
    """Event generated when a proposed change approval has been revoked"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.approval_revoked"


class ProposedChangeRejectionRevokedEvent(ProposedChangeReviewRevokedEvent):
    """Event generated when a proposed change rejection has been revoked"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.rejection_revoked"


class ProposedChangeApprovalsRevokedEvent(ProposedChangeEvent):
    reviewer_accounts: dict[str, str] = Field(
        default_factory=dict, description="ID to name map of accounts whose approval was revoked"
    )

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.approvals_revoked"

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        for account_id, account_name in self.reviewer_accounts.items():
            related.append(
                {
                    "prefect.resource.id": account_id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": InfrahubKind.GENERICACCOUNT,
                    "infrahub.node.id": account_id,
                    "infrahub.reviewer.account.name": account_name,
                }
            )
        return related


class ProposedChangeThreadEvent(ProposedChangeEvent):
    thread_id: str = Field(..., description="The ID of the thread that was created or updated")
    thread_kind: str = Field(..., description="The name of the thread that was created or updated")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.thread_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": self.thread_kind,
                "infrahub.node.id": self.thread_id,
            }
        )
        return related


class ProposedChangeThreadCreatedEvent(ProposedChangeThreadEvent):
    """Event generated when a thread has been created in a proposed change"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change_thread.created"
    action: MutationAction = MutationAction.CREATED


class ProposedChangeThreadUpdatedEvent(ProposedChangeThreadEvent):
    """Event generated when a thread has been updated in a proposed change"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change_thread.updated"
    action: MutationAction = MutationAction.UPDATED
