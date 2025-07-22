from typing import ClassVar

from pydantic import Field

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class ProposedChangeEvent(InfrahubEvent):
    proposed_change_id: str = Field(..., description="The ID of the proposed change")
    proposed_change_name: str = Field(..., description="The name of the proposed change")
    proposed_change_state: str = Field(..., description="The state of the proposed change")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.proposed_change.{self.proposed_change_id}",
            "infrahub.proposed_change.id": self.proposed_change_id,
            "infrahub.proposed_change.name": self.proposed_change_name,
            "infrahub.proposed_change.state": self.proposed_change_state,
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

    def get_resource(self) -> dict[str, str]:
        return {
            **super().get_resource(),
            "infrahub.proposed_change.review_requested_by_account_id": self.requested_by_account_id,
            "infrahub.proposed_change.review_requested_by_account_name": self.requested_by_account_name,
            "infrahub.branch.name": self.meta.context.branch.name,
        }


class ProposedChangeReviewedEvent(ProposedChangeEvent):
    """Event generated when a proposed change has been reviewed"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.reviewed"

    reviewer_account_id: str = Field(..., description="The ID of the user who reviewed the proposed change")
    reviewer_account_name: str = Field(..., description="The name of the user who reviewed the proposed change")
    reviewer_decision: str = Field(..., description="The decision made by the reviewer")

    def get_resource(self) -> dict[str, str]:
        return {
            **super().get_resource(),
            "infrahub.proposed_change.reviewer_account_id": self.reviewer_account_id,
            "infrahub.proposed_change.reviewer_account_name": self.reviewer_account_name,
            "infrahub.proposed_change.reviewer_decision": self.reviewer_decision,
            "infrahub.branch.name": self.meta.context.branch.name,
        }


class ProposedChangeReviewRevokedEvent(ProposedChangeEvent):
    """Event generated when a proposed change review has been revoked"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.review_revoked"

    reviewer_account_id: str = Field(..., description="The ID of the user who reviewed the proposed change")
    reviewer_account_name: str = Field(..., description="The name of the user who reviewed the proposed change")
    reviewer_former_decision: str = Field(..., description="The former decision made by the reviewer")

    def get_resource(self) -> dict[str, str]:
        return {
            **super().get_resource(),
            "infrahub.proposed_change.reviewer_account_id": self.reviewer_account_id,
            "infrahub.proposed_change.reviewer_account_name": self.reviewer_account_name,
            "infrahub.proposed_change.reviewer_former_decision": self.reviewer_former_decision,
            "infrahub.branch.name": self.meta.context.branch.name,
        }


class ProposedChangeMergedEvent(ProposedChangeEvent):
    """Event generated when a proposed change has been merged"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.proposed_change.merged"

    merged_by_account_id: str = Field(..., description="The ID of the user who merged the proposed change")
    merged_by_account_name: str = Field(..., description="The name of the user who merged the proposed change")

    def get_resource(self) -> dict[str, str]:
        return {
            **super().get_resource(),
            "infrahub.proposed_change.merged_by_account_id": self.merged_by_account_id,
            "infrahub.proposed_change.merged_by_account_name": self.merged_by_account_name,
            "infrahub.branch.name": self.meta.context.branch.name,
        }
