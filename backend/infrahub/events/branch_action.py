from pydantic import Field, computed_field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches
from infrahub.message_bus.messages.refresh_registry_rebasedbranch import RefreshRegistryRebasedBranch

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class BranchDeletedEvent(InfrahubEvent):
    """Event generated when a branch has been deleted"""

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

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.branch.deleted"


class BranchCreatedEvent(InfrahubEvent):
    """Event generated when a branch has been created"""

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

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.branch.created"


class BranchMergedEvent(InfrahubEvent):
    """Event generated when a branch has been merged"""

    branch_name: str = Field(..., description="The name of the branch")
    branch_id: str = Field(..., description="The ID of the branch")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.branch.{self.branch_name}",
            "infrahub.branch.id": self.branch_id,
            "infrahub.branch.name": self.branch_name,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return []

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.branch.merged"


class BranchRebasedEvent(InfrahubEvent):
    """Event generated when a branch has been rebased"""

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

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.branch.rebased"
