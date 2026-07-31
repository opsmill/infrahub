from __future__ import annotations

from typing import Any

from infrahub_sdk.protocols import CoreGeneratorDefinition

from infrahub.core.constants import InfrahubKind
from infrahub.core.regeneration.members import run_generator
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.generators.models import (
    ProposedChangeGeneratorDefinition,
    RequestGeneratorDefinitionRun,
    build_generator_definition,
)
from infrahub.git.utils import fetch_proposed_change_generator_definition_targets
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_RUN, TRIGGER_GENERATOR_DEFINITION_RUN

from ..models import LoadedDefinition
from .base import DefinitionSelectorBase


class GeneratorSelector(DefinitionSelectorBase[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun]):
    """Selects the generator definitions flagged to execute after a merge, narrowed to affected members."""

    subscriber_kind = InfrahubKind.GENERATORINSTANCE
    workflow = REQUEST_GENERATOR_DEFINITION_RUN
    full_regeneration_workflow = TRIGGER_GENERATOR_DEFINITION_RUN

    def full_regeneration_parameters(self, *, target_branch: str) -> dict[str, Any]:
        return {"branch": target_branch, "source": GeneratorDefinitionRunSource.MERGE}

    async def load_definitions(
        self, *, target_branch: str
    ) -> list[LoadedDefinition[ProposedChangeGeneratorDefinition]]:
        generators = await self.client.filters(
            kind=CoreGeneratorDefinition,
            prefetch_relationships=True,
            populate_store=True,
            branch=target_branch,
        )
        definitions: list[LoadedDefinition[ProposedChangeGeneratorDefinition]] = []
        for generator in generators:
            if not generator.execute_after_merge.value:
                continue
            definition = build_generator_definition(generator)
            definitions.append(LoadedDefinition(definition=definition, group_id=definition.group_id))
        return definitions

    async def _fetch_member_ids(
        self, *, definition: ProposedChangeGeneratorDefinition, target_branch: str
    ) -> list[str]:
        group = await fetch_proposed_change_generator_definition_targets(
            client=self.client, branch=target_branch, definition=definition
        )
        return [relationship.peer.id for relationship in group.members.peers]

    def _should_render(self, *, subscriber_id: str | None, regenerate_all_members: bool, impacted: list[str]) -> bool:
        return run_generator(
            instance_id=subscriber_id, regenerate_all_members=regenerate_all_members, impacted_instances=impacted
        )

    def _build_request(
        self, *, definition: ProposedChangeGeneratorDefinition, target_branch: str, members: list[str]
    ) -> RequestGeneratorDefinitionRun:
        return RequestGeneratorDefinitionRun(
            branch=target_branch, generator_definition=definition, target_members=members
        )
