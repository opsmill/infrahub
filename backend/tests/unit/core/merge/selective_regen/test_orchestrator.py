from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.merge.selective_regen.definition_selector.base import DefinitionSelectorBase
from infrahub.core.merge.selective_regen.models import DefinitionModel, LoadedDefinition
from infrahub.core.merge.selective_regen.orchestrator import MergeSelectiveRegeneration
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.message_bus.types import ProposedChangeArtifactDefinition
from tests.helpers.diff_summary import node_diff
from tests.helpers.selective_regen import ArtifactForcingSelector, GeneratorForcingSelector

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.models import RegenerationTrigger

TARGET_BRANCH = "main"
REPOSITORY_ID = "repo-1"


class _RecordingSelector[DefinitionT: DefinitionModel, RequestT](DefinitionSelectorBase[DefinitionT, RequestT]):
    """A selector that returns a canned list and records the arguments select was called with."""

    def __init__(self, result: list[RequestT]) -> None:
        self.result = result
        self.calls: list[tuple[list[NodeDiff], str, list[str]]] = []

    async def load_definitions(self, *, target_branch: str) -> list[LoadedDefinition[DefinitionT]]:
        return []

    async def select(
        self,
        *,
        loaded_definitions: list[LoadedDefinition[DefinitionT]],
        forced_repositories: dict[str, RegenerationTrigger],
        diff_summary: list[NodeDiff],
        target_branch: str,
        modified_kinds: list[str],
    ) -> list[RequestT]:
        self.calls.append((diff_summary, target_branch, modified_kinds))
        return self.result

    async def _fetch_member_ids(self, *, definition: DefinitionT, target_branch: str) -> list[str]:
        raise NotImplementedError

    def _should_render(self, *, subscriber_id: str | None, regenerate_all_members: bool, impacted: list[str]) -> bool:
        raise NotImplementedError

    def _build_request(self, *, definition: DefinitionT, target_branch: str, members: list[str]) -> RequestT:
        raise NotImplementedError


def _node_diff(*, node_id: str, kind: str, branch: str = TARGET_BRANCH) -> NodeDiff:
    return node_diff(node_id=node_id, kind=kind, branch=branch)


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


def _generator(*, fingerprint: str | None) -> ProposedChangeGeneratorDefinition:
    return ProposedChangeGeneratorDefinition(
        definition_id="gen-def",
        definition_name="gen",
        query_name="q",
        convert_query_response=False,
        class_name="C",
        file_path="gen.py",
        group_id="grp-1",
        parameters={},
        execute_in_proposed_change=False,
        execute_after_merge=True,
        query_id="q-gen",
        query_models=[],
        query_payload="query {}",
        repository_id=REPOSITORY_ID,
        fingerprint=fingerprint,
        dependencies=[],
        dependencies_complete=True,
    )


def _artifact(*, fingerprint: str | None) -> ProposedChangeArtifactDefinition:
    return ProposedChangeArtifactDefinition(
        definition_id="art-def",
        definition_name="art",
        artifact_name="art",
        query_name="q",
        query_id="q-art",
        query_models=[],
        query_payload="query {}",
        repository_id=REPOSITORY_ID,
        transform_kind="TestTransform",
        content_type="text/plain",
        timeout=30,
        fingerprint=fingerprint,
        dependencies=[],
        dependencies_complete=True,
    )


async def test_missing_generator_fingerprint_escalates_a_sibling_artifact_in_the_same_repository() -> None:
    # A null-fingerprint generator and a populated-fingerprint artifact share a repository. The forced
    # set spans both kinds, so the repository is escalated as a whole: both the generator and the
    # artifact regenerate every member even though the gate rejects them and no subscriber is impacted.
    generator_selector = GeneratorForcingSelector(
        definitions=[_generator(fingerprint=None)],
        member_ids=["m1", "m2"],
        subscriber_by_member={"m1": "s1", "m2": "s2"},
    )
    artifact_selector = ArtifactForcingSelector(
        definitions=[_artifact(fingerprint="fp")],
        member_ids=["m1", "m2"],
        subscriber_by_member={"m1": "s1", "m2": "s2"},
    )

    plan = await MergeSelectiveRegeneration(
        generator_selector=generator_selector, artifact_selector=artifact_selector
    ).build_plan(diff_summary=[], target_branch=TARGET_BRANCH)

    assert [run.target_members for run in plan.generator_runs] == [[]]
    assert [generate.members for generate in plan.artifact_generates] == [[]]
