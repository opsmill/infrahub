from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrahub.core.merge.selective_regen.definition_selector.base import DefinitionSelectorBase
from infrahub.core.merge.selective_regen.gate import DefinitionGate
from infrahub.core.merge.selective_regen.impacted import ImpactedSubscriberResolver
from infrahub.core.merge.selective_regen.models import (
    CascadeRole,
    CascadeSourceOutput,
    DefinitionModel,
    GateResult,
    LoadedDefinition,
)
from infrahub.core.regeneration.models import TargetSelection
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.message_bus.types import ProposedChangeArtifactDefinition
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE, REQUEST_GENERATOR_DEFINITION_RUN

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.timestamp import Timestamp


class StubCascadeSourceOutput:
    """A CascadeSourceOutput that captures nothing, for source doubles that only exercise selection."""

    async def capture(self, *, since: Timestamp) -> list[NodeDiff]:
        return []


class RecordingGeneratorDiffCapturer:
    """A GeneratorMutationDiffCapturer double: records its calls and returns its diff unchanged."""

    def __init__(self) -> None:
        self.calls: list[tuple[Timestamp, list[str]]] = []
        self.result: list[NodeDiff] = []

    async def capture(self, *, since: Timestamp, generator_definition_names: list[str]) -> list[NodeDiff]:
        self.calls.append((since, generator_definition_names))
        return self.result


class RejectingGate(DefinitionGate):
    """A gate that selects nothing, so only the untrusted-signal fallback can force a definition."""

    def __init__(self) -> None:
        pass

    def evaluate(
        self, *, definition: object, diff_summary: list[NodeDiff], modified_kinds: list[str], group_id: str
    ) -> GateResult:
        return GateResult(regenerate_all_members=False, selected=False)


class NoImpactResolver(ImpactedSubscriberResolver):
    """A resolver that reports no impacted subscribers."""

    def __init__(self) -> None:
        pass

    async def resolve(
        self,
        *,
        query_payload: str,
        diff_summary: list[NodeDiff],
        target_branch: str,
        subscriber_kind: str,
        every_target: list[str],
    ) -> TargetSelection:
        return TargetSelection(ids=[], widened=False)


class ForcingTemplateSelector[DefinitionT: DefinitionModel, RequestT](DefinitionSelectorBase[DefinitionT, RequestT]):
    """Runs the real select template with a rejecting gate and no impacted subscribers.

    Only the untrusted-signal fallback can produce a request, so the result isolates whether a
    definition is force-regenerated rather than selected by the diff.
    """

    subscriber_kind = "TestSubscriber"

    def __init__(
        self, *, definitions: list[DefinitionT], member_ids: list[str], subscriber_by_member: dict[str, str]
    ) -> None:
        self.gate = RejectingGate()
        self.impacted_resolver = NoImpactResolver()
        self.log = logging.getLogger("test_selective_regen")
        self._definitions = definitions
        self._member_ids = member_ids
        self._subscriber_by_member = subscriber_by_member

    async def load_definitions(self, *, target_branch: str) -> list[LoadedDefinition[DefinitionT]]:
        return [LoadedDefinition(definition=definition, group_id="grp-1") for definition in self._definitions]

    async def _map_subscribers_by_member(self, *, definition: DefinitionT, target_branch: str) -> dict[str, str]:
        return self._subscriber_by_member

    async def _fetch_member_ids(self, *, definition: DefinitionT, target_branch: str) -> list[str]:
        return self._member_ids

    def _should_render(self, *, subscriber_id: str | None, regenerate_all_members: bool, impacted: list[str]) -> bool:
        return not subscriber_id or regenerate_all_members or subscriber_id in impacted


class GeneratorForcingSelector(
    ForcingTemplateSelector[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun]
):
    workflow = REQUEST_GENERATOR_DEFINITION_RUN
    cascade_role = CascadeRole.SOURCE

    def output_capture(self, requests: Sequence[RequestGeneratorDefinitionRun]) -> CascadeSourceOutput:
        return StubCascadeSourceOutput()

    def _build_request(
        self, *, definition: ProposedChangeGeneratorDefinition, target_branch: str, members: list[str]
    ) -> RequestGeneratorDefinitionRun:
        return RequestGeneratorDefinitionRun(
            branch=target_branch, generator_definition=definition, target_members=members
        )


class ArtifactForcingSelector(
    ForcingTemplateSelector[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate]
):
    workflow = REQUEST_ARTIFACT_DEFINITION_GENERATE
    cascade_role = CascadeRole.TERMINAL

    def _build_request(
        self, *, definition: ProposedChangeArtifactDefinition, target_branch: str, members: list[str]
    ) -> RequestArtifactDefinitionGenerate:
        return RequestArtifactDefinitionGenerate(
            branch=target_branch,
            artifact_definition_id=definition.definition_id,
            artifact_definition_name=definition.definition_name,
            members=members,
        )
