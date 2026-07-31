from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.regeneration_dispatcher import PostMergeRegenerationDispatcher
from infrahub.core.merge.selective_regen.models import (
    CascadeRole,
    FullRegeneration,
    PlannedRegeneration,
    SelectiveRegenerationPlan,
)
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.workflows.catalogue import (
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from infrahub.core.timestamp import Timestamp
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition

DIFF_ID = "diff-1"
TARGET_BRANCH = "main"


def _summary_cache(cache: MemoryCache) -> DiffSummaryCache:
    return DiffSummaryCache(cache=cache, serializer=DiffSummarySerializer(), key_namespace="branch_merge")


def _plan(
    *,
    generator_runs: list[RequestGeneratorDefinitionRun] | None = None,
    artifact_generates: list[RequestArtifactDefinitionGenerate] | None = None,
    source_output: _FakeSourceOutput | None = None,
) -> SelectiveRegenerationPlan:
    """Build a plan the way the orchestrator does: one entry per planner, tagged by cascade role."""
    return SelectiveRegenerationPlan(
        entries=[
            PlannedRegeneration(
                workflow=REQUEST_GENERATOR_DEFINITION_RUN,
                cascade_role=CascadeRole.SOURCE,
                requests=generator_runs or [],
                output=source_output,
            ),
            PlannedRegeneration(
                workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                cascade_role=CascadeRole.TERMINAL,
                requests=artifact_generates or [],
            ),
        ]
    )


def _submitted_entry(requests: list[RequestArtifactDefinitionGenerate]) -> PlannedRegeneration:
    return PlannedRegeneration(
        workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, cascade_role=CascadeRole.TERMINAL, requests=requests
    )


class _FakePlanner:
    """A RegenerationPlanner that returns a canned plan or raises, recording its invocations."""

    def __init__(
        self,
        *,
        plan: SelectiveRegenerationPlan | None = None,
        error: Exception | None = None,
        artifact_plan: list[RequestArtifactDefinitionGenerate] | None = None,
        submissions: list[PlannedRegeneration] | None = None,
    ) -> None:
        self._plan = plan
        self._error = error
        self._artifact_plan = artifact_plan or []
        self._submissions = submissions
        self.calls = 0
        self.reselect_diffs: list[list] = []

    async def build_plan(self, diff_summary: list, target_branch: str) -> SelectiveRegenerationPlan:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._plan if self._plan is not None else _plan()

    async def reselect_from_cascade_output(self, diff_summary: list, target_branch: str) -> list[PlannedRegeneration]:
        self.reselect_diffs.append(diff_summary)
        return [_submitted_entry(self._artifact_plan)]

    def consolidate_submissions(self, entries: Sequence[PlannedRegeneration]) -> list[PlannedRegeneration]:
        """Return the canned submissions when set, otherwise the entries unchanged."""
        return self._submissions if self._submissions is not None else list(entries)

    def terminal_full_regenerations(self, target_branch: str) -> list[FullRegeneration]:
        """The blanket regeneration a single artifact terminal would contribute."""
        return [FullRegeneration(workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE, parameters={"branch": target_branch})]


class _FakeSourceOutput:
    """A CascadeSourceOutput returning a canned diff or raising, recording its capture calls."""

    def __init__(self, *, diff_summary: list | None = None, error: Exception | None = None) -> None:
        self._diff_summary = diff_summary if diff_summary is not None else []
        self._error = error
        self.calls = 0

    async def capture(self, *, since: Timestamp, requests: Sequence[Any]) -> list:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._diff_summary


class _FailingGeneratorRecorder(WorkflowRecorder):
    """Records calls but raises on one generator definition's execute, to exercise failure isolation."""

    def __init__(self, *, fail_definition: str) -> None:
        super().__init__()
        self._fail_definition = fail_definition

    async def execute_workflow(  # noqa: PLR0913, PLR0917
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> Any:
        result = await super().execute_workflow(
            workflow,
            expected_return=expected_return,
            context=context,
            parameters=parameters,
            tags=tags,
            priority=priority,
        )
        if (
            workflow == REQUEST_GENERATOR_DEFINITION_RUN
            and (parameters or {})["model"].generator_definition.definition_name == self._fail_definition
        ):
            raise RuntimeError("generator boom")
        return result


def _context() -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name=TARGET_BRANCH),
        account=AccountSession(account_id="test-account", auth_type=AuthType.API),
    )


def _plan_with_one_of_each(source_output: _FakeSourceOutput | None = None) -> SelectiveRegenerationPlan:
    generator_definition = ProposedChangeGeneratorDefinition(
        definition_id="gd1",
        definition_name="gen",
        query_name="q",
        convert_query_response=False,
        class_name="Gen",
        file_path="gen.py",
        group_id="group-1",
        parameters={},
        execute_in_proposed_change=False,
        execute_after_merge=True,
        query_id="q1",
        query_models=["TestDevice"],
        query_payload="query { TestDevice { edges { node { id } } } }",
        repository_id="repo-1",
    )
    return _plan(
        generator_runs=[RequestGeneratorDefinitionRun(branch=TARGET_BRANCH, generator_definition=generator_definition)],
        artifact_generates=[
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art"
            )
        ],
        source_output=source_output,
    )


def _generator_run(*, definition_id: str) -> RequestGeneratorDefinitionRun:
    generator_definition = ProposedChangeGeneratorDefinition(
        definition_id=definition_id,
        definition_name=definition_id,
        query_name="q",
        convert_query_response=False,
        class_name="Gen",
        file_path="gen.py",
        group_id="group-1",
        parameters={},
        execute_in_proposed_change=False,
        execute_after_merge=True,
        query_id="q1",
        query_models=["TestDevice"],
        query_payload="query { TestDevice { edges { node { id } } } }",
        repository_id="repo-1",
    )
    return RequestGeneratorDefinitionRun(branch=TARGET_BRANCH, generator_definition=generator_definition)


def _plan_with_two_generators(source_output: _FakeSourceOutput | None = None) -> SelectiveRegenerationPlan:
    return _plan(
        generator_runs=[_generator_run(definition_id="gd1"), _generator_run(definition_id="gd2")],
        artifact_generates=[
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art"
            )
        ],
        source_output=source_output,
    )


def _plan_with_only_artifacts() -> SelectiveRegenerationPlan:
    return _plan(
        artifact_generates=[
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art"
            )
        ],
    )


def _dispatcher(
    planner: _FakePlanner,
    cache: DiffSummaryCache,
    recorder: WorkflowRecorder,
) -> PostMergeRegenerationDispatcher:
    return PostMergeRegenerationDispatcher(
        workflow=recorder,
        planner=planner,
        summary_cache=cache,
        log=logging.getLogger("test"),
    )


@pytest.fixture(autouse=True)
def enable_selective() -> Iterator[None]:
    original = config.SETTINGS.main.selective_execution_after_merge
    config.SETTINGS.main.selective_execution_after_merge = True
    yield
    config.SETTINGS.main.selective_execution_after_merge = original


@pytest.fixture
def disable_selective() -> Iterator[None]:
    original = config.SETTINGS.main.selective_execution_after_merge
    config.SETTINGS.main.selective_execution_after_merge = False
    yield
    config.SETTINGS.main.selective_execution_after_merge = original


def _full_regen_submitted(recorder: WorkflowRecorder) -> bool:
    return (
        len(recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)) == 1
        and len(recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN)) == 1
    )


async def test_flag_off_submits_full_regeneration(disable_selective: None) -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # Flag off reproduces the prior blanket path exactly, without consulting the planner.
    assert _full_regen_submitted(recorder)
    assert recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)[0]["parameters"] == {
        "branch": TARGET_BRANCH
    }
    assert recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN)[0]["parameters"] == {
        "branch": TARGET_BRANCH,
        "source": GeneratorDefinitionRunSource.MERGE,
    }
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []
    assert recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_RUN) == []
    assert planner.calls == 0


async def test_missing_key_submits_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=None
    )

    assert _full_regen_submitted(recorder)
    assert planner.calls == 0


async def test_cache_miss_submits_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())  # never seeded

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert _full_regen_submitted(recorder)
    assert planner.calls == 0


async def test_malformed_summary_submits_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan_with_one_of_each())
    memory = MemoryCache()
    memory.storage[f"branch_merge:diff_id:{DIFF_ID}:diff_summary"] = "{not-valid-json"
    cache = _summary_cache(memory)

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert _full_regen_submitted(recorder)
    assert planner.calls == 0
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []


async def test_empty_plan_dispatches_nothing() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan())
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert recorder.submit_calls == []


async def test_selection_failure_falls_back_to_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(error=RuntimeError("boom"))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert planner.calls == 1
    assert _full_regen_submitted(recorder)
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []


def _targeted_artifact() -> RequestArtifactDefinitionGenerate:
    return RequestArtifactDefinitionGenerate(
        branch=TARGET_BRANCH, artifact_definition_id="ad2", artifact_definition_name="targeted-art"
    )


async def test_merge_targets_artifacts_from_generator_output() -> None:
    recorder = WorkflowRecorder()
    source_output = _FakeSourceOutput(diff_summary=[{"kind": "TestDevice"}])
    planner = _FakePlanner(
        plan=_plan_with_one_of_each(source_output=source_output), artifact_plan=[_targeted_artifact()]
    )
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # The generator is awaited (not submitted), its output is captured by the source itself, and the
    # terminals are selected from that captured diff -- alongside the merge-diff artifact -- with no
    # blanket regeneration.
    assert [call["workflow"] for call in recorder.execute_calls] == [REQUEST_GENERATOR_DEFINITION_RUN]
    assert recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_RUN) == []
    assert source_output.calls == 1
    assert planner.reselect_diffs == [[{"kind": "TestDevice"}]]
    submitted = [
        call["parameters"]["model"].artifact_definition_name
        for call in recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
    ]
    assert submitted == ["art", "targeted-art"]
    assert recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []


async def test_awaits_every_generator_before_capturing_output() -> None:
    recorder = WorkflowRecorder()
    source_output = _FakeSourceOutput(diff_summary=[{"kind": "TestDevice"}])
    planner = _FakePlanner(plan=_plan_with_two_generators(source_output=source_output))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # Both generators are awaited before the single capture; racing the tail would capture against a
    # partially-mutated graph.
    assert source_output.calls == 1
    assert [(call["kind"], call["workflow"]) for call in recorder.calls] == [
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN),
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN),
        ("submit", REQUEST_ARTIFACT_DEFINITION_GENERATE),
    ]


async def test_merge_without_generator_keeps_selective_artifacts() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan_with_only_artifacts())
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # No source ran, so no output is captured and the artifact selection stays narrow.
    assert planner.reselect_diffs == []
    assert len(recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)) == 1
    assert recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []
    assert recorder.execute_calls == []


async def test_generator_output_capture_failure_falls_back_to_blanket_artifacts() -> None:
    recorder = WorkflowRecorder()
    source_output = _FakeSourceOutput(error=RuntimeError("capture boom"))
    planner = _FakePlanner(plan=_plan_with_one_of_each(source_output=source_output))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert [call["workflow"] for call in recorder.execute_calls] == [REQUEST_GENERATOR_DEFINITION_RUN]
    assert [
        call["parameters"]["branch"] for call in recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)
    ] == [TARGET_BRANCH]
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []
    assert recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN) == []


async def test_generator_run_failure_is_isolated_and_regenerates_artifacts_not_generators() -> None:
    recorder = _FailingGeneratorRecorder(fail_definition="gd1")
    source_output = _FakeSourceOutput(diff_summary=[{"kind": "TestDevice"}])
    planner = _FakePlanner(plan=_plan_with_two_generators(source_output=source_output))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # gd1 fails but gd2 is still attempted: the failure is isolated, not allowed to abort the loop.
    ran = [
        call["parameters"]["model"].generator_definition.definition_name
        for call in recorder.get_execute_calls_for(REQUEST_GENERATOR_DEFINITION_RUN)
    ]
    assert ran == ["gd1", "gd2"]
    assert [
        call["parameters"]["branch"] for call in recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)
    ] == [TARGET_BRANCH]
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []
    assert recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN) == []
    # A failed generator short-circuits to blanket regeneration; its output is never captured.
    assert source_output.calls == 0


async def test_merge_submits_what_the_planner_consolidates() -> None:
    """The dispatcher submits exactly the entries the planner's consolidation returns, via their workflow.

    Consolidating the requests (deduping a definition selected by more than one diff) is the planner's
    job, unit-tested on the planner; here the dispatcher must submit that result verbatim.
    """
    recorder = WorkflowRecorder()
    consolidated = [
        _submitted_entry(
            [
                RequestArtifactDefinitionGenerate(
                    branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art"
                ),
                RequestArtifactDefinitionGenerate(
                    branch=TARGET_BRANCH, artifact_definition_id="ad2", artifact_definition_name="art2"
                ),
            ]
        )
    ]
    source_output = _FakeSourceOutput(diff_summary=[{"kind": "TestDevice"}])
    planner = _FakePlanner(plan=_plan_with_one_of_each(source_output=source_output), submissions=consolidated)
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    submitted = [
        call["parameters"]["model"].artifact_definition_id
        for call in recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
    ]
    assert submitted == ["ad1", "ad2"]
