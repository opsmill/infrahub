from typing import Any

from pydantic import Field, computed_field

from infrahub.message_bus import InfrahubMessage

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class CommitUpdatedEvent(InfrahubEvent):
    """Event generated when the the commit within a repository has been updated."""

    commit: str = Field(..., description="The commit the repository was updated to")
    repository_id: str = Field(..., description="The ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.repository.{self.repository_id}",
            "infrahub.repository.name": self.repository_name,
            "infrahub.repository.id": self.repository_id,
        }

    def get_payload(self) -> dict[str, Any]:
        return {
            "commit": self.commit,
            "repository_id": self.repository_id,
            "repository_name": self.repository_name,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return []

    @computed_field
    def event_name(self) -> str:
        return f"{EVENT_NAMESPACE}.repository.update_commit"
