from typing import ClassVar

from pydantic import Field

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


class ArtifactCreatedEvent(ArtifactEvent):
    """Event generated when an artifact has been created"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.artifact.created"
    infrahub_node_kind_event: ClassVar[bool] = True


class ArtifactUpdatedEvent(ArtifactEvent):
    """Event generated when an artifact has been updated"""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.artifact.updated"
    infrahub_node_kind_event: ClassVar[bool] = True
