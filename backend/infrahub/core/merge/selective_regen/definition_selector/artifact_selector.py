from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreArtifactDefinition

from infrahub.core.constants import InfrahubKind
from infrahub.core.regeneration.definitions import GATHER_ARTIFACT_DEFINITIONS, parse_artifact_definitions
from infrahub.core.regeneration.members import should_render_artifact
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.git.utils import fetch_artifact_definition_targets
from infrahub.message_bus.types import ProposedChangeArtifactDefinition
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE

from ..models import CascadeRole, LoadedDefinition
from .base import DefinitionSelectorBase

if TYPE_CHECKING:
    from collections.abc import Sequence


class ArtifactSelector(DefinitionSelectorBase[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate]):
    """Selects the artifact definitions a merge changed, narrowed to the members it affects."""

    subscriber_kind = InfrahubKind.ARTIFACT
    workflow = REQUEST_ARTIFACT_DEFINITION_GENERATE
    cascade_role = CascadeRole.TERMINAL

    def consolidate(
        self, requests: Sequence[RequestArtifactDefinitionGenerate]
    ) -> list[RequestArtifactDefinitionGenerate]:
        """Merge requests for the same artifact definition, unioning their member/limit filters.

        An artifact selected from both the merge diff and a generator's output would otherwise be
        dispatched twice; an empty filter means "all members", so it subsumes any specific filter.
        """
        consolidated: dict[str, RequestArtifactDefinitionGenerate] = {}
        for request in requests:
            merged = consolidated.get(request.artifact_definition_id)
            if merged is None:
                consolidated[request.artifact_definition_id] = request
                continue
            members = [] if not merged.members or not request.members else sorted({*merged.members, *request.members})
            limit = [] if not merged.limit or not request.limit else sorted({*merged.limit, *request.limit})
            consolidated[request.artifact_definition_id] = merged.model_copy(
                update={"members": members, "limit": limit}
            )
        return list(consolidated.values())

    async def load_definitions(self, *, target_branch: str) -> list[LoadedDefinition[ProposedChangeArtifactDefinition]]:
        definition_information = await self.client.execute_graphql(
            query=GATHER_ARTIFACT_DEFINITIONS, branch_name=target_branch
        )
        edges = definition_information[InfrahubKind.ARTIFACTDEFINITION]["edges"]
        # A definition with no target group cannot be reconciled against members; skip it rather than
        # crash the whole selection (which would fall the entire merge back to blanket regeneration).
        loaded: list[LoadedDefinition[ProposedChangeArtifactDefinition]] = []
        for edge in edges:
            targets = edge["node"]["targets"]
            target_node = targets["node"] if targets else None
            if target_node is None:
                self.log.warning(
                    f"Artifact definition {edge['node']['id']} has no target group; "
                    "excluding it from selective regeneration"
                )
                continue
            loaded.extend(
                LoadedDefinition(definition=definition, group_id=target_node["id"])
                for definition in parse_artifact_definitions(definitions=[edge])
            )
        return loaded

    async def _fetch_member_ids(self, *, definition: ProposedChangeArtifactDefinition, target_branch: str) -> list[str]:
        definition_node = await self.client.get(
            kind=CoreArtifactDefinition, id=definition.definition_id, branch=target_branch, include=["targets"]
        )
        group = await fetch_artifact_definition_targets(
            client=self.client, branch=target_branch, definition=definition_node
        )
        return [relationship.peer.id for relationship in group.members.peers]

    def _should_render(self, *, subscriber_id: str | None, regenerate_all_members: bool, impacted: list[str]) -> bool:
        return should_render_artifact(
            artifact_id=subscriber_id, regenerate_all_members=regenerate_all_members, impacted_artifacts=impacted
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
