from typing import Any

from pydantic import Field

from infrahub.message_bus import InfrahubMessage

from .models import InfrahubBranchEvent


class CommitUpdatedEvent(InfrahubBranchEvent):
    """Event generated when the the commit within a repository has been updated."""

    commit: str = Field(..., description="The commit the repository was updated to")
    repository_id: str = Field(..., description="The ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")

    def get_name(self) -> str:
        return f"{self.get_event_namespace()}.repository.update_commit"

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.repository.{self.repository_id}",
            "infrahub.branch.name": self.branch,
            "infrahub.repository.name": self.repository_name,
            "infrahub.repository.id": self.repository_id,
        }

    def get_payload(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "commit": self.commit,
            "repository_id": self.repository_id,
            "repository_name": self.repository_name,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return []
