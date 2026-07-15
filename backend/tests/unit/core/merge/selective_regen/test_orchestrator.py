from __future__ import annotations

from infrahub_sdk.diff import NodeDiff

from infrahub.core.merge.selective_regen.definition_selector.base import DefinitionSelectorBase
from infrahub.core.merge.selective_regen.models import DefinitionModel, LoadedDefinition
from infrahub.core.merge.selective_regen.orchestrator import MergeSelectiveRegeneration
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.message_bus.types import ProposedChangeArtifactDefinition

TARGET_BRANCH = "main"


class _RecordingSelector[DefinitionT: DefinitionModel, RequestT](DefinitionSelectorBase[DefinitionT, RequestT]):
    """A selector that returns a canned list and records the arguments it was called with.

    Overrides the template's entry point directly, so the kind-specific hooks are never reached.
    """

    def __init__(self, result: list[RequestT]) -> None:
        self.result = result
        self.calls: list[tuple[list[NodeDiff], str, list[str]]] = []

    async def select(
        self, *, diff_summary: list[NodeDiff], target_branch: str, modified_kinds: list[str]
    ) -> list[RequestT]:
        self.calls.append((diff_summary, target_branch, modified_kinds))
        return self.result

    async def _load_definitions(self, *, target_branch: str) -> list[LoadedDefinition[DefinitionT]]:
        raise NotImplementedError

    async def _fetch_member_ids(self, *, definition: DefinitionT, target_branch: str) -> list[str]:
        raise NotImplementedError

    def _should_render(self, *, subscriber_id: str | None, managed_branch: bool, impacted: list[str]) -> bool:
        raise NotImplementedError

    def _build_request(self, *, definition: DefinitionT, target_branch: str, members: list[str]) -> RequestT:
        raise NotImplementedError


def _node_diff(*, node_id: str, kind: str, branch: str = TARGET_BRANCH) -> NodeDiff:
    return NodeDiff(branch=branch, kind=kind, id=node_id, action="UPDATED", display_label="node", elements=[])


async def test_build_plan_shares_modified_kinds_and_assembles_plan() -> None:
    diff_summary = [
        _node_diff(node_id="n1", kind="TestDevice"),
        _node_diff(node_id="n2", kind="TestSite"),
        _node_diff(node_id="n3", kind="TestDevice"),
        _node_diff(node_id="n4", kind="Ignored", branch="other-branch"),
    ]
    artifact_request = RequestArtifactDefinitionGenerate(
        artifact_definition_id="art-1", artifact_definition_name="art", branch=TARGET_BRANCH, members=["m1"]
    )
    generator_selector = _RecordingSelector[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun](result=[])
    artifact_selector = _RecordingSelector[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate](
        result=[artifact_request]
    )

    plan = await MergeSelectiveRegeneration(
        generator_selector=generator_selector, artifact_selector=artifact_selector
    ).build_plan(diff_summary=diff_summary, target_branch=TARGET_BRANCH)

    # Each selector's output lands in its own field of the plan.
    assert plan.generator_runs == []
    assert plan.artifact_generates == [artifact_request]

    # modified_kinds is computed once off the target branch (the other-branch entry is excluded) and
    # the same diff, branch and kinds reach both selectors.
    for selector in (generator_selector, artifact_selector):
        assert len(selector.calls) == 1
        recorded_diff, recorded_branch, recorded_kinds = selector.calls[0]
        assert recorded_diff is diff_summary
        assert recorded_branch == TARGET_BRANCH
        assert set(recorded_kinds) == {"TestDevice", "TestSite"}
