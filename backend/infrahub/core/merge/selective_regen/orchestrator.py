from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.proposed_change.branch_diff import get_modified_kinds

from .definition_selector.artifact_selector import ArtifactSelector
from .definition_selector.generator_selector import GeneratorSelector
from .gate import DefinitionGate
from .impacted import ImpactedSubscriberResolver
from .models import SelectiveRegenerationPlan

if TYPE_CHECKING:
    import logging

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
    from infrahub.git.models import RequestArtifactDefinitionGenerate
    from infrahub.message_bus.types import ProposedChangeArtifactDefinition

    from .definition_selector.base import DefinitionSelectorBase


class RegenerationSelector(Protocol):
    """Computes which definitions and members a merge diff requires be regenerated."""

    async def build_plan(self, diff_summary: list[NodeDiff], target_branch: str) -> SelectiveRegenerationPlan: ...


class MergeSelectiveRegeneration:
    """Select the generator and artifact definitions a merge changed, narrowed to affected members.

    Orchestrates the generator and artifact selectors over a single computation of the diff's
    modified kinds, returning the combined plan a merge follow-up should dispatch.
    """

    def __init__(
        self,
        generator_selector: DefinitionSelectorBase[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun],
        artifact_selector: DefinitionSelectorBase[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate],
    ) -> None:
        self.generator_selector = generator_selector
        self.artifact_selector = artifact_selector

    async def build_plan(self, diff_summary: list[NodeDiff], target_branch: str) -> SelectiveRegenerationPlan:
        modified_kinds = get_modified_kinds(diff_summary=diff_summary, branch=target_branch)
        generator_runs = await self.generator_selector.select(
            diff_summary=diff_summary, target_branch=target_branch, modified_kinds=modified_kinds
        )
        artifact_generates = await self.artifact_selector.select(
            diff_summary=diff_summary, target_branch=target_branch, modified_kinds=modified_kinds
        )
        return SelectiveRegenerationPlan(generator_runs=generator_runs, artifact_generates=artifact_generates)


def build_merge_selective_regeneration(
    *,
    client: InfrahubClient,
    log: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> MergeSelectiveRegeneration:
    """Wire a fully-injected selector for one merge follow-up, sharing the gate and impact resolver."""
    gate = DefinitionGate(log=log)
    impacted_resolver = ImpactedSubscriberResolver(client=client)
    return MergeSelectiveRegeneration(
        generator_selector=GeneratorSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log),
        artifact_selector=ArtifactSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log),
    )
