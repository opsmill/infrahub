from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.merge.selective_regen.definition_selector.base import DefinitionSelectorBase
from infrahub.core.merge.selective_regen.models import (
    CascadeRole,
    DefinitionModel,
    LoadedDefinition,
    PlannedRegeneration,
    SelectiveRegenerationPlan,
)
from infrahub.core.merge.selective_regen.orchestrator import MergeSelectiveRegeneration
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.message_bus.types import ProposedChangeArtifactDefinition
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE, REQUEST_GENERATOR_DEFINITION_RUN
from tests.helpers.diff_summary import node_diff
from tests.helpers.selective_regen import (
    AppendingExpander,
    ArtifactForcingSelector,
    GeneratorForcingSelector,
    PassthroughExpander,
    StubCascadeSourceOutput,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.merge.selective_regen.models import CascadeSourceOutput
    from infrahub.core.regeneration.models import RegenerationTrigger
    from infrahub.workflows.models import WorkflowDefinition

TARGET_BRANCH = "main"
REPOSITORY_ID = "repo-1"


class _RecordingSelector[DefinitionT: DefinitionModel, RequestT](DefinitionSelectorBase[DefinitionT, RequestT]):
    """A selector that returns a canned list and records the arguments select was called with."""

    def __init__(
        self,
        result: list[RequestT],
        *,
        workflow: WorkflowDefinition,
        cascade_role: CascadeRole,
        output: CascadeSourceOutput | None = None,
    ) -> None:
        self.result = result
        self.workflow = workflow
        self.cascade_role = cascade_role
        self._output = output
        self.calls: list[tuple[list[NodeDiff], str, list[str]]] = []
        self.consolidate_calls: list[list[RequestT]] = []

    def output_capture(self, requests: Sequence[RequestT]) -> CascadeSourceOutput | None:
        return self._output

    def consolidate(self, requests: Sequence[RequestT]) -> Sequence[RequestT]:
        self.consolidate_calls.append(list(requests))
        return requests

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


def _entry(cascade_role: CascadeRole) -> PlannedRegeneration:
    workflow = (
        REQUEST_GENERATOR_DEFINITION_RUN if cascade_role is CascadeRole.SOURCE else REQUEST_ARTIFACT_DEFINITION_GENERATE
    )
    return PlannedRegeneration(workflow=workflow, cascade_role=cascade_role, requests=[])


def test_for_role_returns_the_entries_playing_that_role_in_order() -> None:
    """for_role selects the plan entries whose selector plays the given role, preserving their order."""
    source = _entry(CascadeRole.SOURCE)
    first_terminal = _entry(CascadeRole.TERMINAL)
    second_terminal = _entry(CascadeRole.TERMINAL)
    plan = SelectiveRegenerationPlan(entries=[source, first_terminal, second_terminal])

    assert plan.for_role(CascadeRole.SOURCE) == [source]
    assert plan.for_role(CascadeRole.TERMINAL) == [first_terminal, second_terminal]


async def test_build_plan_rejects_a_cascade_source_without_an_output_capture() -> None:
    """A SOURCE that produces no output capture would silently skip the cascade, so the plan is rejected.

    Failing fast at plan construction turns a misconfigured new source into a caught error and safe full
    regeneration, rather than a source that runs but whose terminals are never reselected.
    """
    source_without_output = _RecordingSelector[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun](
        result=[], workflow=REQUEST_GENERATOR_DEFINITION_RUN, cascade_role=CascadeRole.SOURCE, output=None
    )

    with pytest.raises(
        ValueError,
        match=(
            r"^cascade source 'request-generator-definition-run' produced no output capture; "
            r"a source must capture the output its terminals reselect from$"
        ),
    ):
        await MergeSelectiveRegeneration(
            selectors=[source_without_output], kinds_expander=PassthroughExpander()
        ).build_plan(diff_summary=[], target_branch=TARGET_BRANCH)


async def test_build_plan_rejects_a_cascade_terminal_carrying_an_output_capture() -> None:
    """A TERMINAL that captures output is a wiring error, since only a source feeds the cascade."""
    terminal_with_output = _RecordingSelector[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate](
        result=[],
        workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
        cascade_role=CascadeRole.TERMINAL,
        output=StubCascadeSourceOutput(),
    )

    with pytest.raises(
        ValueError,
        match=(
            r"^cascade terminal 'request_artifact_definitions_generate' produced an output capture; "
            r"only a source feeds the cascade$"
        ),
    ):
        await MergeSelectiveRegeneration(
            selectors=[terminal_with_output], kinds_expander=PassthroughExpander()
        ).build_plan(diff_summary=[], target_branch=TARGET_BRANCH)


async def test_build_plan_shares_modified_kinds_and_assembles_plan() -> None:
    """build_plan computes the modified kinds once and returns one entry per selector, in order."""
    diff_summary = [
        _node_diff(node_id="n1", kind="TestDevice"),
        _node_diff(node_id="n2", kind="TestSite"),
        _node_diff(node_id="n3", kind="TestDevice"),
        _node_diff(node_id="n4", kind="Ignored", branch="other-branch"),
    ]
    artifact_request = RequestArtifactDefinitionGenerate(
        artifact_definition_id="art-1", artifact_definition_name="art", branch=TARGET_BRANCH, members=["m1"]
    )
    generator_output = StubCascadeSourceOutput()
    generator_selector = _RecordingSelector[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun](
        result=[], workflow=REQUEST_GENERATOR_DEFINITION_RUN, cascade_role=CascadeRole.SOURCE, output=generator_output
    )
    artifact_selector = _RecordingSelector[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate](
        result=[artifact_request],
        workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
        cascade_role=CascadeRole.TERMINAL,
    )

    plan = await MergeSelectiveRegeneration(
        selectors=[generator_selector, artifact_selector], kinds_expander=PassthroughExpander()
    ).build_plan(diff_summary=diff_summary, target_branch=TARGET_BRANCH)

    assert [(entry.workflow, entry.cascade_role, entry.requests, entry.output) for entry in plan.entries] == [
        (REQUEST_GENERATOR_DEFINITION_RUN, CascadeRole.SOURCE, [], generator_output),
        (REQUEST_ARTIFACT_DEFINITION_GENERATE, CascadeRole.TERMINAL, [artifact_request], None),
    ]

    # modified_kinds is computed once off the target branch (the other-branch entry is excluded) and
    # the same diff, branch and kinds reach both selectors.
    for selector in (generator_selector, artifact_selector):
        assert len(selector.calls) == 1
        recorded_diff, recorded_branch, recorded_kinds = selector.calls[0]
        assert recorded_diff is diff_summary
        assert recorded_branch == TARGET_BRANCH
        assert set(recorded_kinds) == {"TestDevice", "TestSite"}


async def test_build_plan_passes_expanded_kinds_to_selectors() -> None:
    """The kinds the expander widens the diff to are the kinds every selector receives."""
    diff_summary = [_node_diff(node_id="n1", kind="TestDevice")]
    generator_selector = _RecordingSelector[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun](
        result=[],
        workflow=REQUEST_GENERATOR_DEFINITION_RUN,
        cascade_role=CascadeRole.SOURCE,
        output=StubCascadeSourceOutput(),
    )
    artifact_selector = _RecordingSelector[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate](
        result=[], workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, cascade_role=CascadeRole.TERMINAL
    )

    await MergeSelectiveRegeneration(
        selectors=[generator_selector, artifact_selector], kinds_expander=AppendingExpander(extra_kind="TestProfiled")
    ).build_plan(diff_summary=diff_summary, target_branch=TARGET_BRANCH)

    for selector in (generator_selector, artifact_selector):
        _, _, recorded_kinds = selector.calls[0]
        assert set(recorded_kinds) == {"TestDevice", "TestProfiled"}


async def test_reselect_from_cascade_output_excludes_cascade_sources() -> None:
    """The diff of a cascade source's own writes re-runs only the non-source selectors.

    Re-running a source on the diff it produced would repeat a run already completed.
    """
    diff_summary = [_node_diff(node_id="n1", kind="TestDevice")]
    artifact_request = RequestArtifactDefinitionGenerate(
        artifact_definition_id="art-1", artifact_definition_name="art", branch=TARGET_BRANCH, members=["m1"]
    )
    generator_selector = _RecordingSelector[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun](
        result=[], workflow=REQUEST_GENERATOR_DEFINITION_RUN, cascade_role=CascadeRole.SOURCE
    )
    artifact_selector = _RecordingSelector[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate](
        result=[artifact_request], workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, cascade_role=CascadeRole.TERMINAL
    )

    entries = await MergeSelectiveRegeneration(
        selectors=[generator_selector, artifact_selector], kinds_expander=PassthroughExpander()
    ).reselect_from_cascade_output(diff_summary=diff_summary, target_branch=TARGET_BRANCH)

    assert generator_selector.calls == []
    assert len(artifact_selector.calls) == 1
    assert [(entry.workflow, entry.cascade_role, entry.requests) for entry in entries] == [
        (REQUEST_ARTIFACT_DEFINITION_GENERATE, CascadeRole.TERMINAL, [artifact_request]),
    ]


async def test_reselect_from_cascade_output_escalates_across_terminals_sharing_a_repository() -> None:
    """A null-fingerprint terminal escalates its whole repository, including a sibling terminal.

    The missing-fingerprint set is aggregated over every non-source selector before selection, so it
    keeps the repository-wide fallback build_plan applies rather than escalating each kind in isolation.
    """
    unpopulated_terminal = ArtifactForcingSelector(
        definitions=[_artifact(fingerprint=None)], member_ids=["m1"], subscriber_by_member={"m1": "s1"}
    )
    populated_terminal = ArtifactForcingSelector(
        definitions=[_artifact(fingerprint="fp")], member_ids=["m2"], subscriber_by_member={"m2": "s2"}
    )

    entries = await MergeSelectiveRegeneration(
        selectors=[unpopulated_terminal, populated_terminal], kinds_expander=PassthroughExpander()
    ).reselect_from_cascade_output(diff_summary=[], target_branch=TARGET_BRANCH)

    assert [len(entry.requests) for entry in entries] == [1, 1]


async def test_consolidate_submissions_routes_each_workflow_to_its_selector() -> None:
    """Each entry's requests are consolidated by the selector that owns its workflow, then tagged back."""
    generator_selector = _RecordingSelector[ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun](
        result=[], workflow=REQUEST_GENERATOR_DEFINITION_RUN, cascade_role=CascadeRole.SOURCE
    )
    artifact_selector = _RecordingSelector[ProposedChangeArtifactDefinition, RequestArtifactDefinitionGenerate](
        result=[], workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, cascade_role=CascadeRole.TERMINAL
    )
    generator_run = RequestGeneratorDefinitionRun(
        branch=TARGET_BRANCH, generator_definition=_generator(fingerprint="fp")
    )
    artifact_request = RequestArtifactDefinitionGenerate(
        artifact_definition_id="ad1", artifact_definition_name="art", branch=TARGET_BRANCH
    )
    entries = [
        PlannedRegeneration(
            workflow=REQUEST_GENERATOR_DEFINITION_RUN, cascade_role=CascadeRole.SOURCE, requests=[generator_run]
        ),
        PlannedRegeneration(
            workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
            cascade_role=CascadeRole.TERMINAL,
            requests=[artifact_request],
        ),
    ]

    result = MergeSelectiveRegeneration(
        selectors=[generator_selector, artifact_selector], kinds_expander=PassthroughExpander()
    ).consolidate_submissions(entries)

    assert generator_selector.consolidate_calls == [[generator_run]]
    assert artifact_selector.consolidate_calls == [[artifact_request]]
    assert [(entry.workflow, list(entry.requests)) for entry in result] == [
        (REQUEST_GENERATOR_DEFINITION_RUN, [generator_run]),
        (REQUEST_ARTIFACT_DEFINITION_GENERATE, [artifact_request]),
    ]


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
    """A null-fingerprint definition escalates its whole repository across every kind.

    A null-fingerprint generator and a populated-fingerprint artifact share a repository, so both
    regenerate every member even though the gate rejects them and no subscriber is impacted.
    """
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
        selectors=[generator_selector, artifact_selector], kinds_expander=PassthroughExpander()
    ).build_plan(diff_summary=[], target_branch=TARGET_BRANCH)

    generator_entries = plan.for_role(CascadeRole.SOURCE)
    artifact_entries = plan.for_role(CascadeRole.TERMINAL)
    generator_runs = [
        run for entry in generator_entries for run in entry.requests if isinstance(run, RequestGeneratorDefinitionRun)
    ]
    artifact_generates = [
        generate
        for entry in artifact_entries
        for generate in entry.requests
        if isinstance(generate, RequestArtifactDefinitionGenerate)
    ]
    assert [run.target_members for run in generator_runs] == [[]]
    assert [generate.members for generate in artifact_generates] == [[]]
