from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreGeneratorDefinition

from infrahub.core.constants import InfrahubKind
from infrahub.core.regeneration.members import run_generator
from infrahub.generators.models import (
    ProposedChangeGeneratorDefinition,
    RequestGeneratorDefinitionRun,
    build_generator_definition,
)
from infrahub.git.utils import fetch_proposed_change_generator_definition_targets
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_RUN

from ..generator_diff_capturer import GeneratorTrackingOutput
from ..models import CascadeRole, CascadeSourceOutput, LoadedDefinition
from .base import DefinitionSelectorBase

if TYPE_CHECKING:
    import logging
    from collections.abc import Sequence

    from infrahub_sdk.client import InfrahubClient

    from ..gate import DefinitionGate
    from ..generator_diff_capturer import GeneratorMutationDiffCapturer
    from ..impacted import ImpactedSubscriberResolver


class GeneratorSelector(DefinitionSelectorBase[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun]):
    """Selects the generator definitions flagged to execute after a merge, narrowed to affected members."""

    subscriber_kind = InfrahubKind.GENERATORINSTANCE
    workflow = REQUEST_GENERATOR_DEFINITION_RUN
    cascade_role = CascadeRole.SOURCE

    def __init__(
        self,
        client: InfrahubClient,
        gate: DefinitionGate,
        impacted_resolver: ImpactedSubscriberResolver,
        log: logging.Logger | logging.LoggerAdapter[logging.Logger],
        output_capturer: GeneratorMutationDiffCapturer,
    ) -> None:
        super().__init__(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log)
        self._output_capturer = output_capturer

    def output_capture(self, requests: Sequence[RequestGeneratorDefinitionRun]) -> CascadeSourceOutput:
        return GeneratorTrackingOutput(
            capturer=self._output_capturer,
            definition_names=[run.generator_definition.definition_name for run in requests],
        )

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
