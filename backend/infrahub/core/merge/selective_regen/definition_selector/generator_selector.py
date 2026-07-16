from __future__ import annotations

from infrahub.core.constants import InfrahubKind
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.git.utils import fetch_proposed_change_generator_definition_targets
from infrahub.proposed_change.tasks import _run_generator

from ..models import LoadedDefinition
from .base import DefinitionSelectorBase


class GeneratorSelector(DefinitionSelectorBase[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun]):
    """Selects the generator definitions flagged to execute after a merge, narrowed to affected members."""

    subscriber_kind = InfrahubKind.GENERATORINSTANCE

    async def _load_definitions(
        self, *, target_branch: str
    ) -> list[LoadedDefinition[ProposedChangeGeneratorDefinition]]:
        generators = await self.client.filters(
            kind=InfrahubKind.GENERATORDEFINITION,
            prefetch_relationships=True,
            populate_store=True,
            branch=target_branch,
        )
        definitions: list[LoadedDefinition[ProposedChangeGeneratorDefinition]] = []
        for generator in generators:
            if not generator.execute_after_merge.value:
                continue
            definition = ProposedChangeGeneratorDefinition(
                definition_id=generator.id,
                definition_name=generator.name.value,
                class_name=generator.class_name.value,
                file_path=generator.file_path.value,
                query_name=generator.query.peer.name.value,
                query_id=generator.query.peer.id,
                query_models=generator.query.peer.models.value,
                query_payload=generator.query.peer.query.value,
                repository_id=generator.repository.peer.id,
                parameters=generator.parameters.value,
                group_id=generator.targets.peer.id,
                convert_query_response=generator.convert_query_response.value,
                execute_in_proposed_change=generator.execute_in_proposed_change.value,
                execute_after_merge=generator.execute_after_merge.value,
                dependencies=generator.dependencies.value,
                dependencies_complete=generator.dependencies_complete.value,
            )
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
        return _run_generator(
            instance_id=subscriber_id, managed_branch=regenerate_all_members, impacted_instances=impacted
        )

    def _build_request(
        self, *, definition: ProposedChangeGeneratorDefinition, target_branch: str, members: list[str]
    ) -> RequestGeneratorDefinitionRun:
        return RequestGeneratorDefinitionRun(
            branch=target_branch, generator_definition=definition, target_members=members
        )
