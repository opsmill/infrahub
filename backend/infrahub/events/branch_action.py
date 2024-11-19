from pydantic import Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.event_branch_delete import EventBranchDelete
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches

from .models import InfrahubBranchEvent


class BranchDeleteEvent(InfrahubBranchEvent):
    """Event generated when a branch has been deleted"""

    branch_id: str = Field(..., description="The ID of the mutated node")
    sync_with_git: bool = Field(..., description="Indicates if the branch was extended to Git")

    def get_name(self) -> str:
        return f"{self.get_event_namespace()}.branch.deleted"

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.branch.{self.branch}",
            "infrahub.branch.id": self.branch_id,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        events = [
            EventBranchDelete(
                branch=self.branch,
                branch_id=self.branch_id,
                sync_with_git=self.sync_with_git,
                meta=self.get_message_meta(),
            ),
            RefreshRegistryBranches(),
        ]
        return events
