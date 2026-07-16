from __future__ import annotations

from infrahub_sdk.protocols import CoreArtifactDefinition

from infrahub.core.constants import InfrahubKind
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.git.utils import fetch_artifact_definition_targets
from infrahub.message_bus.types import ProposedChangeArtifactDefinition
from infrahub.proposed_change.tasks import (
    GATHER_ARTIFACT_DEFINITIONS,
    _parse_artifact_definitions,
    _should_render_artifact,
)

from ..models import LoadedDefinition
from .base import DefinitionSelectorBase


class ArtifactSelector(DefinitionSelectorBase[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate]):
    """Selects the artifact definitions a merge changed, narrowed to the members it affects."""

    subscriber_kind = InfrahubKind.ARTIFACT

    async def _load_definitions(
        self, *, target_branch: str
    ) -> list[LoadedDefinition[ProposedChangeArtifactDefinition]]:
        definition_information = await self.client.execute_graphql(
            query=GATHER_ARTIFACT_DEFINITIONS, branch_name=target_branch
        )
        edges = definition_information[InfrahubKind.ARTIFACTDEFINITION]["edges"]
        # A definition with no target group cannot be reconciled against members; skip it rather than
        # crash the whole selection (which would fall the entire merge back to blanket regeneration).
        group_id_by_definition: dict[str, str] = {}
        selectable_edges = []
        for edge in edges:
            targets = edge["node"]["targets"]
            target_node = targets["node"] if targets else None
            if target_node is None:
                self.log.warning(
                    f"Artifact definition {edge['node']['id']} has no target group; "
                    "excluding it from selective regeneration"
                )
                continue
            group_id_by_definition[edge["node"]["id"]] = target_node["id"]
            selectable_edges.append(edge)
        return [
            LoadedDefinition(definition=definition, group_id=group_id_by_definition[definition.definition_id])
            for definition in _parse_artifact_definitions(definitions=selectable_edges)
        ]

    async def _fetch_member_ids(self, *, definition: ProposedChangeArtifactDefinition, target_branch: str) -> list[str]:
        definition_node = await self.client.get(
            kind=CoreArtifactDefinition, id=definition.definition_id, branch=target_branch, include=["targets"]
        )
        group = await fetch_artifact_definition_targets(
            client=self.client, branch=target_branch, definition=definition_node
        )
        return [relationship.peer.id for relationship in group.members.peers]

    def _should_render(self, *, subscriber_id: str | None, regenerate_all_members: bool, impacted: list[str]) -> bool:
        return _should_render_artifact(
            artifact_id=subscriber_id, managed_branch=regenerate_all_members, impacted_artifacts=impacted
        )

    def _build_request(
        self, *, definition: ProposedChangeArtifactDefinition, target_branch: str, members: list[str]
    ) -> RequestArtifactDefinitionGenerate:
        return RequestArtifactDefinitionGenerate(
            branch=target_branch,
            artifact_definition_id=definition.definition_id,
            artifact_definition_name=definition.definition_name,
            members=members,
        )
