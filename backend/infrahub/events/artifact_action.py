from typing import Any

from pydantic import Field, computed_field

from infrahub.message_bus import InfrahubMessage

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class ArtifactEvent(InfrahubEvent):
    """Event generated when an artifact has been created or updated."""

    node_id: str = Field(..., description="The ID of the artifact")
    artifact_definition_id: str = Field(..., description="The ID of the artifact definition")
    target_id: str = Field(..., description="The ID of the target of the artifact")
    target_kind: str = Field(..., description="The kind of the target of the artifact")
    checksum: str = Field(..., description="The current checksum of the artifact")
    checksum_previous: str | None = Field(default=None, description="The previous checksum of the artifact")
    storage_id: str = Field(..., description="The current storage id of the artifact")
    storage_id_previous: str | None = Field(default=None, description="The previous storage id of the artifact")
    created: bool = Field(..., description="Indicates if the artifact was created with this event or already existed")

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        related.append(
            {
                "prefect.resource.id": self.target_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": self.target_kind,
            }
        )
        related.append(
            {
                "prefect.resource.id": self.target_id,
                "prefect.resource.role": "infrahub.artifact",
                "infrahub.artifact.checksum": self.checksum,
                "infrahub.artifact.checksum_previous": self.checksum_previous or "",
                "infrahub.artifact.storage_id": self.storage_id,
                "infrahub.artifact.storage_id_previous": self.storage_id_previous or "",
                "infrahub.artifact.artifact_definition_id": self.artifact_definition_id,
            }
        )

        return related

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": self.node_id,
            "infrahub.node.kind": "CoreArtifact",
            "infrahub.node.id": self.node_id,
            "infrahub.branch.name": self.meta.context.branch.name,
        }

    def get_payload(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "artifact_definition_id": self.artifact_definition_id,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "checksum": self.checksum,
            "checksum_previous": self.checksum_previous,
            "storage_id": self.storage_id,
            "storage_id_previous": self.storage_id_previous,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return []

    @computed_field
    def event_name(self) -> str:
        match self.created:
            case True:
                return f"{EVENT_NAMESPACE}.artifact.created"
            case False:
                return f"{EVENT_NAMESPACE}.artifact.updated"
