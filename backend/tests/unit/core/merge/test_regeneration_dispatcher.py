from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import FullRegenerationReason
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.regeneration_barrier import NarrowedHoldCache, RegenerationBarrier
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
from infrahub.git.writeback.constants import NARROWED_HOLD_MAX_BYTES, NARROWED_HOLD_TTL_SECONDS
from infrahub.git.writeback.models import HeldItem, HeldRegeneration, HeldWiden, PendingMerge
from infrahub.workflows.catalogue import (
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.workflow import WorkflowRecorder
from tests.unit.git.writeback.fakes import FixedClock, InMemoryDeliveryState

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from infrahub.core.timestamp import Timestamp
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition

DIFF_ID = "diff-1"
TARGET_BRANCH = "main"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
REPOSITORY_X = "repository-x"
REPOSITORY_Y = "repository-y"
COMMIT = "0123456789abcdef0123456789abcdef01234567"


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


def _generator_run(*, definition_id: str, repository_id: str = "repo-1") -> RequestGeneratorDefinitionRun:
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
        repository_id=repository_id,
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


async def _no_wait(delay: float) -> None:
    """Return at once; no case here makes the delivery state fail."""


def _delivery_state() -> InMemoryDeliveryState:
    return InMemoryDeliveryState(
        clock=FixedClock(now=NOW), repository_names={REPOSITORY_X: REPOSITORY_X, REPOSITORY_Y: REPOSITORY_Y}
    )


async def _pending_delivery_state(*repository_ids: str) -> InMemoryDeliveryState:
    """Queue one merge for each repository, so that each one has a pending delivery."""
    state = _delivery_state()
    for repository_id in repository_ids:
        await state.enqueue(
            repository_id=repository_id,
            entry=PendingMerge(
                entry_id=f"{repository_id}-merge",
                source_branch="feature",
                source_git_branch="feature",
                source_commit=COMMIT,
                merged_at=NOW,
            ),
            widen=False,
        )
    state.calls.clear()
    return state


def _dispatcher(
    planner: _FakePlanner,
    cache: DiffSummaryCache,
    recorder: WorkflowRecorder,
    state: InMemoryDeliveryState | None = None,
) -> PostMergeRegenerationDispatcher:
    """Build the dispatcher; with no state, no repository has a pending delivery."""
    return PostMergeRegenerationDispatcher(
        workflow=recorder,
        planner=planner,
        summary_cache=cache,
        barrier=RegenerationBarrier(
            state=_delivery_state() if state is None else state,
            narrowed=NarrowedHoldCache(
                cache=MemoryCache(), ttl_seconds=NARROWED_HOLD_TTL_SECONDS, max_bytes=NARROWED_HOLD_MAX_BYTES
            ),
            default_branch_name=TARGET_BRANCH,
            sleep=_no_wait,
        ),
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=None, releasing=None
    )

    assert _full_regen_submitted(recorder)
    assert planner.calls == 0


async def test_cache_miss_submits_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())  # never seeded

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
    )

    assert recorder.submit_calls == []


async def test_selection_failure_falls_back_to_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    planner = _FakePlanner(error=RuntimeError("boom"))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
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
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
    )

    submitted = [
        call["parameters"]["model"].artifact_definition_id
        for call in recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
    ]
    assert submitted == ["ad1", "ad2"]


def _artifact(*, definition_id: str, repository_id: str) -> RequestArtifactDefinitionGenerate:
    return RequestArtifactDefinitionGenerate(
        branch=TARGET_BRANCH,
        artifact_definition_id=definition_id,
        artifact_definition_name=definition_id,
        repository_id=repository_id,
    )


def _held(*, artifacts: tuple[str, ...] = (), generators: tuple[str, ...] = ()) -> HeldRegeneration:
    """The held set after one hold of these definitions."""
    return HeldRegeneration(
        next_hold_seq=2,
        artifact_definitions=tuple(HeldItem(id=definition_id, hold_seq=1) for definition_id in artifacts),
        generator_definitions=tuple(HeldItem(id=definition_id, hold_seq=1) for definition_id in generators),
    )


def _held_marker(*, scope: Literal["all", "terminals"], reason: FullRegenerationReason) -> HeldRegeneration:
    """The held set after one hold of the marker."""
    return HeldRegeneration(next_hold_seq=2, widen=HeldWiden(scope=scope, reason=reason, hold_seq=1))


def _held_by_repository(state: InMemoryDeliveryState) -> dict[str, HeldRegeneration]:
    return {repository_id: state.intents[repository_id].held for repository_id in (REPOSITORY_X, REPOSITORY_Y)}


def _submitted_artifact_ids(recorder: WorkflowRecorder) -> list[str]:
    return [
        call["parameters"]["model"].artifact_definition_id
        for call in recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
    ]


async def test_the_plan_holds_the_work_of_a_pending_repository_and_dispatches_the_rest() -> None:
    state = await _pending_delivery_state(REPOSITORY_X)
    recorder = WorkflowRecorder()
    planner = _FakePlanner(
        plan=_plan(
            generator_runs=[
                _generator_run(definition_id="gd-x", repository_id=REPOSITORY_X),
                _generator_run(definition_id="gd-y", repository_id=REPOSITORY_Y),
            ],
            artifact_generates=[
                _artifact(definition_id="ad-x", repository_id=REPOSITORY_X),
                _artifact(definition_id="ad-y", repository_id=REPOSITORY_Y),
            ],
            source_output=_FakeSourceOutput(diff_summary=[{"kind": "TestDevice"}]),
        )
    )
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder, state=state).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
    )

    assert [
        call["parameters"]["model"].generator_definition.definition_id
        for call in recorder.get_execute_calls_for(REQUEST_GENERATOR_DEFINITION_RUN)
    ] == ["gd-y"]
    assert _submitted_artifact_ids(recorder) == ["ad-y"]
    assert recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []
    assert recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN) == []
    assert state.calls == ["pending_repository_ids", "hold"]
    assert _held_by_repository(state) == {
        REPOSITORY_X: _held(artifacts=("ad-x",), generators=("gd-x",)),
        REPOSITORY_Y: HeldRegeneration(),
    }


async def test_an_artifact_of_a_pending_repository_reselected_after_the_cascade_is_held() -> None:
    state = await _pending_delivery_state(REPOSITORY_X)
    recorder = WorkflowRecorder()
    planner = _FakePlanner(
        plan=_plan(
            generator_runs=[_generator_run(definition_id="gd-y", repository_id=REPOSITORY_Y)],
            artifact_generates=[_artifact(definition_id="ad-y", repository_id=REPOSITORY_Y)],
            source_output=_FakeSourceOutput(diff_summary=[{"kind": "TestDevice"}]),
        ),
        artifact_plan=[
            _artifact(definition_id="ad-x-reselected", repository_id=REPOSITORY_X),
            _artifact(definition_id="ad-y-reselected", repository_id=REPOSITORY_Y),
        ],
    )
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder, state=state).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
    )

    assert _submitted_artifact_ids(recorder) == ["ad-y", "ad-y-reselected"]
    # The plan holds nothing of the pending repository; the reselected artifact is held after the cascade.
    assert state.calls == ["pending_repository_ids", "pending_repository_ids", "hold"]
    assert _held_by_repository(state) == {
        REPOSITORY_X: _held(artifacts=("ad-x-reselected",)),
        REPOSITORY_Y: HeldRegeneration(),
    }


async def test_the_releasing_repository_dispatches_its_work_while_another_pending_repository_holds() -> None:
    state = await _pending_delivery_state(REPOSITORY_X, REPOSITORY_Y)
    recorder = WorkflowRecorder()
    planner = _FakePlanner(
        plan=_plan(
            artifact_generates=[
                _artifact(definition_id="ad-x", repository_id=REPOSITORY_X),
                _artifact(definition_id="ad-y", repository_id=REPOSITORY_Y),
            ]
        )
    )
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder, state=state).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=REPOSITORY_X
    )

    assert _submitted_artifact_ids(recorder) == ["ad-x"]
    assert state.calls == ["pending_repository_ids", "hold"]
    assert _held_by_repository(state) == {
        REPOSITORY_X: HeldRegeneration(),
        REPOSITORY_Y: _held(artifacts=("ad-y",)),
    }


@dataclass
class FullRegenerationTestCase:
    name: str
    pending: tuple[str, ...]
    reason: FullRegenerationReason
    expected_artifact_parameters: dict[str, Any]
    expected_generator_parameters: dict[str, Any]
    expected_calls: list[str]
    expected_held: dict[str, HeldRegeneration]
    releasing: str | None = None
    selective: bool = True
    merge_diff_cache_key: str | None = None
    planner_error: Exception | None = None


FULL_REGENERATION_TEST_CASES: list[FullRegenerationTestCase] = [
    FullRegenerationTestCase(
        name="no_pending_delivery_submits_the_blanket_parameters",
        pending=(),
        reason=FullRegenerationReason.NO_SUMMARY_CAPTURED,
        expected_artifact_parameters={"branch": TARGET_BRANCH},
        expected_generator_parameters={"branch": TARGET_BRANCH, "source": GeneratorDefinitionRunSource.MERGE},
        expected_calls=["pending_repository_ids"],
        expected_held={REPOSITORY_X: HeldRegeneration(), REPOSITORY_Y: HeldRegeneration()},
    ),
    FullRegenerationTestCase(
        name="a_missing_summary_holds_a_marker_for_the_pending_repository_and_excludes_it",
        pending=(REPOSITORY_X,),
        reason=FullRegenerationReason.NO_SUMMARY_CAPTURED,
        expected_artifact_parameters={"branch": TARGET_BRANCH, "exclude_repository_ids": [REPOSITORY_X]},
        expected_generator_parameters={
            "branch": TARGET_BRANCH,
            "source": GeneratorDefinitionRunSource.MERGE,
            "exclude_repository_ids": [REPOSITORY_X],
        },
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={
            REPOSITORY_X: _held_marker(scope="all", reason=FullRegenerationReason.NO_SUMMARY_CAPTURED),
            REPOSITORY_Y: HeldRegeneration(),
        },
    ),
    FullRegenerationTestCase(
        name="a_failed_selection_holds_a_marker_with_its_own_reason",
        pending=(REPOSITORY_X,),
        reason=FullRegenerationReason.SELECTION_FAILED,
        merge_diff_cache_key=DIFF_ID,
        planner_error=RuntimeError("boom"),
        expected_artifact_parameters={"branch": TARGET_BRANCH, "exclude_repository_ids": [REPOSITORY_X]},
        expected_generator_parameters={
            "branch": TARGET_BRANCH,
            "source": GeneratorDefinitionRunSource.MERGE,
            "exclude_repository_ids": [REPOSITORY_X],
        },
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={
            REPOSITORY_X: _held_marker(scope="all", reason=FullRegenerationReason.SELECTION_FAILED),
            REPOSITORY_Y: HeldRegeneration(),
        },
    ),
    FullRegenerationTestCase(
        name="the_flag_off_holds_a_marker_with_the_feature_disabled_reason",
        pending=(REPOSITORY_X,),
        reason=FullRegenerationReason.FEATURE_DISABLED,
        selective=False,
        merge_diff_cache_key=DIFF_ID,
        expected_artifact_parameters={"branch": TARGET_BRANCH, "exclude_repository_ids": [REPOSITORY_X]},
        expected_generator_parameters={
            "branch": TARGET_BRANCH,
            "source": GeneratorDefinitionRunSource.MERGE,
            "exclude_repository_ids": [REPOSITORY_X],
        },
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={
            REPOSITORY_X: _held_marker(scope="all", reason=FullRegenerationReason.FEATURE_DISABLED),
            REPOSITORY_Y: HeldRegeneration(),
        },
    ),
    FullRegenerationTestCase(
        name="the_releasing_repository_is_neither_held_nor_excluded",
        pending=(REPOSITORY_X, REPOSITORY_Y),
        releasing=REPOSITORY_X,
        reason=FullRegenerationReason.NO_SUMMARY_CAPTURED,
        expected_artifact_parameters={"branch": TARGET_BRANCH, "exclude_repository_ids": [REPOSITORY_Y]},
        expected_generator_parameters={
            "branch": TARGET_BRANCH,
            "source": GeneratorDefinitionRunSource.MERGE,
            "exclude_repository_ids": [REPOSITORY_Y],
        },
        expected_calls=["pending_repository_ids", "hold"],
        expected_held={
            REPOSITORY_X: HeldRegeneration(),
            REPOSITORY_Y: _held_marker(scope="all", reason=FullRegenerationReason.NO_SUMMARY_CAPTURED),
        },
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FULL_REGENERATION_TEST_CASES])
async def test_a_full_regeneration_holds_a_marker_for_each_pending_repository_and_excludes_it(
    test_case: FullRegenerationTestCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "selective_execution_after_merge", test_case.selective)
    state = await _pending_delivery_state(*test_case.pending)
    recorder = WorkflowRecorder()
    planner = _FakePlanner(plan=_plan_with_one_of_each(), error=test_case.planner_error)
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder, state=state).dispatch(
        context=_context(),
        target_branch=TARGET_BRANCH,
        merge_diff_cache_key=test_case.merge_diff_cache_key,
        releasing=test_case.releasing,
    )

    assert [call["parameters"] for call in recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)] == [
        test_case.expected_artifact_parameters
    ]
    assert [call["parameters"] for call in recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN)] == [
        test_case.expected_generator_parameters
    ]
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []
    assert state.calls == test_case.expected_calls
    assert _held_by_repository(state) == test_case.expected_held


@dataclass
class TerminalRegenerationTestCase:
    name: str
    generator_fails: bool
    capture_fails: bool


TERMINAL_REGENERATION_TEST_CASES: list[TerminalRegenerationTestCase] = [
    TerminalRegenerationTestCase(name="a_failed_generator_run", generator_fails=True, capture_fails=False),
    TerminalRegenerationTestCase(
        name="a_failed_capture_of_the_generator_output", generator_fails=False, capture_fails=True
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TERMINAL_REGENERATION_TEST_CASES])
async def test_a_terminal_regeneration_holds_a_terminals_marker_for_each_pending_repository_and_excludes_it(
    test_case: TerminalRegenerationTestCase,
) -> None:
    state = await _pending_delivery_state(REPOSITORY_X)
    recorder = _FailingGeneratorRecorder(fail_definition="gd-y" if test_case.generator_fails else "")
    source_output = _FakeSourceOutput(
        diff_summary=[{"kind": "TestDevice"}],
        error=RuntimeError("capture boom") if test_case.capture_fails else None,
    )
    planner = _FakePlanner(
        plan=_plan(
            generator_runs=[_generator_run(definition_id="gd-y", repository_id=REPOSITORY_Y)],
            artifact_generates=[_artifact(definition_id="ad-y", repository_id=REPOSITORY_Y)],
            source_output=source_output,
        )
    )
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(planner, cache, recorder, state=state).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID, releasing=None
    )

    assert [call["parameters"] for call in recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)] == [
        {"branch": TARGET_BRANCH, "exclude_repository_ids": [REPOSITORY_X]}
    ]
    assert recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN) == []
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []
    assert state.calls == ["pending_repository_ids", "pending_repository_ids", "hold"]
    assert _held_by_repository(state) == {
        REPOSITORY_X: _held_marker(scope="terminals", reason=FullRegenerationReason.TERMINAL_SELECTION_FAILED),
        REPOSITORY_Y: HeldRegeneration(),
    }
