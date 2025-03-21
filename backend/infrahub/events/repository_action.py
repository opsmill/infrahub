from typing import ClassVar

from pydantic import Field

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class CommitUpdatedEvent(InfrahubEvent):
    """Event generated when the the commit within a repository has been updated."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.repository.update_commit"

    commit: str = Field(..., description="The commit the repository was updated to")
    repository_id: str = Field(..., description="The ID of the repository")
    repository_name: str = Field(..., description="The name of the repository")

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.repository.{self.repository_id}",
            "infrahub.repository.name": self.repository_name,
            "infrahub.repository.id": self.repository_id,
            "infrahub.branch.name": self.meta.context.branch.name,
        }
