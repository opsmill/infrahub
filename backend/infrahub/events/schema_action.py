from typing import Any

from pydantic import Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches

from .models import InfrahubBranchEvent


class SchemaUpdatedEvent(InfrahubBranchEvent):
    """Event generated when the schema within a branch has been updated."""

    schema_hash: str = Field(..., description="Schema hash after the update")

    def get_name(self) -> str:
        return f"{self.get_event_namespace()}.schema.update"

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.schema_branch.{self.branch}",
            "infrahub.branch.name": self.branch,
            "infrahub.branch.schema_hash": self.schema_hash,
        }

    def get_payload(self) -> dict[str, Any]:
        return {"branch": self.branch, "schema_hash": self.schema_hash}

    def get_messages(self) -> list[InfrahubMessage]:
        return [
            RefreshRegistryBranches(),
            # EventSchemaUpdate(
            #     branch=self.branch,
            #     meta=self.get_message_meta(),
            # )
        ]
