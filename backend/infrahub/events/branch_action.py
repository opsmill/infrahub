from typing import ClassVar

from pydantic import Field

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches
from infrahub.message_bus.messages.refresh_registry_rebasedbranch import RefreshRegistryRebasedBranch

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class BranchDeletedEvent(InfrahubEvent):
    """Event generated when a branch has been deleted"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.branch.deleted"

    branch_name: str = Field(..., description="The name of the branch")
    branch_id: str = Field(..., description="The ID of the mutated node")
    sync_with_git: bool = Field(..., description="Indicates if the branch was extended to Git")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.branch.{self.branch_name}",
            "infrahub.branch.id": self.branch_id,
            "infrahub.branch.name": self.branch_name,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        events: list[InfrahubMessage] = [
            # EventBranchDelete(
            #     branch=self.branch,
            #     branch_id=self.branch_id,
            #     sync_with_git=self.sync_with_git,
            #     meta=self.get_message_meta(),
            # ),
            RefreshRegistryBranches(),
        ]
        return events


class BranchCreatedEvent(InfrahubEvent):
    """Event generated when a branch has been created"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.branch.created"

    branch_name: str = Field(..., description="The name of the branch")
    branch_id: str = Field(..., description="The ID of the branch")
    sync_with_git: bool = Field(..., description="Indicates if the branch was extended to Git")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.branch.{self.branch_name}",
            "infrahub.branch.id": self.branch_id,
            "infrahub.branch.name": self.branch_name,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        events: list[InfrahubMessage] = [
            # EventBranchCreate(
            #     branch=self.branch,
            #     branch_id=self.branch_id,
            #     sync_with_git=self.sync_with_git,
            #     meta=self.get_message_meta(),
            # ),
            RefreshRegistryBranches(),
        ]
        return events


class BranchMergedEvent(InfrahubEvent):
    """Event generated when a branch has been merged"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.branch.merged"

    branch_name: str = Field(..., description="The name of the branch")
    branch_id: str = Field(..., description="The ID of the branch")
    proposed_change_id: str | None = Field(
        default=None, description="The ID of the proposed change that merged this branch if applicable"
    )

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.branch.{self.branch_name}",
            "infrahub.branch.id": self.branch_id,
            "infrahub.branch.name": self.branch_name,
        }

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        if self.proposed_change_id:
            related.append(
                {
                    "prefect.resource.id": self.proposed_change_id,
                    "prefect.resource.role": "infrahub.related.node",
                    "infrahub.node.kind": InfrahubKind.PROPOSEDCHANGE,
                }
            )

        return related

    def get_messages(self) -> list[InfrahubMessage]:
        return [RefreshRegistryBranches()]


class BranchRebasedEvent(InfrahubEvent):
    """Event generated when a branch has been rebased"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.branch.rebased"

    branch_id: str = Field(..., description="The ID of the mutated node")
    branch_name: str = Field(..., description="The name of the branch")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.branch.{self.branch_name}",
            "infrahub.branch.id": self.branch_id,
            "infrahub.branch.name": self.branch_name,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        events: list[InfrahubMessage] = [
            # EventBranchRebased(
            #     branch=self.branch,
            #     meta=self.get_message_meta(),
            # ),
            RefreshRegistryRebasedBranch(branch=self.branch_name),
        ]
        return events
