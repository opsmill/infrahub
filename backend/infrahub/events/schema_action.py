from typing import ClassVar

from pydantic import Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class SchemaUpdatedEvent(InfrahubEvent):
    """Event generated when the schema within a branch has been updated."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.schema.updated"

    branch_name: str = Field(..., description="The name of the branch")
    schema_hash: str = Field(..., description="Schema hash after the update")

    # NOTE
    # We could add to the payload
    # - Hash before and after the change
    # - List of nodes and generics that have been modified
    # - Diff of the change

    # NOTE 2
    # Should schema_update be a branch event ?
    # if feels like the main resource should be the branch

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.schema_branch.{self.branch_name}",
            "infrahub.branch.name": self.branch_name,
            "infrahub.branch.schema_hash": self.schema_hash,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return [
            RefreshRegistryBranches(),
            # EventSchemaUpdate(
            #     branch=self.branch,
            #     meta=self.get_message_meta(),
            # )
        ]
