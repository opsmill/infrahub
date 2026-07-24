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
from infrahub.core.merge.selective_regen.models import SelectiveRegenerationPlan
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
    from collections.abc import Iterator

    from infrahub.core.timestamp import Timestamp
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition

DIFF_ID = "diff-1"
TARGET_BRANCH = "main"


def _summary_cache(cache: MemoryCache) -> DiffSummaryCache:
    return DiffSummaryCache(cache=cache, serializer=DiffSummarySerializer(), key_namespace="branch_merge")


class _FakeSelector:
    """A RegenerationSelector that returns a canned plan or raises, recording its invocations."""

    def __init__(
        self,
        *,
        plan: SelectiveRegenerationPlan | None = None,
        error: Exception | None = None,
        artifact_plan: list[RequestArtifactDefinitionGenerate] | None = None,
    ) -> None:
        self._plan = plan
        self._error = error
        self._artifact_plan = artifact_plan or []
        self.calls = 0
        self.select_artifacts_diffs: list[list] = []

    async def build_plan(self, diff_summary: list, target_branch: str) -> SelectiveRegenerationPlan:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return (
            self._plan
            if self._plan is not None
            else SelectiveRegenerationPlan(generator_runs=[], artifact_generates=[])
        )

    async def select_artifacts(self, diff_summary: list, target_branch: str) -> list[RequestArtifactDefinitionGenerate]:
        self.select_artifacts_diffs.append(diff_summary)
        return self._artifact_plan


class _FakeCapturer:
    """A GeneratorMutationDiffCapturer returning a canned diff summary or raising, recording its calls."""

    def __init__(self, *, diff_summary: list | None = None, error: Exception | None = None) -> None:
        self._diff_summary = diff_summary if diff_summary is not None else []
        self._error = error
        self.calls = 0
        self.definition_names: list[list[str]] = []

    async def capture(self, *, since: Timestamp, generator_definition_names: list[str]) -> list:
        self.calls += 1
        self.definition_names.append(generator_definition_names)
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


def _plan_with_one_of_each() -> SelectiveRegenerationPlan:
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
    return SelectiveRegenerationPlan(
        generator_runs=[RequestGeneratorDefinitionRun(branch=TARGET_BRANCH, generator_definition=generator_definition)],
        artifact_generates=[
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art"
            )
        ],
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


def _plan_with_two_generators() -> SelectiveRegenerationPlan:
    return SelectiveRegenerationPlan(
        generator_runs=[_generator_run(definition_id="gd1"), _generator_run(definition_id="gd2")],
        artifact_generates=[
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art"
            )
        ],
    )


def _plan_with_only_artifacts() -> SelectiveRegenerationPlan:
    return SelectiveRegenerationPlan(
        generator_runs=[],
        artifact_generates=[
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art"
            )
        ],
    )


def _dispatcher(
    selector: _FakeSelector,
    cache: DiffSummaryCache,
    recorder: WorkflowRecorder,
    capturer: _FakeCapturer | None = None,
) -> PostMergeRegenerationDispatcher:
    return PostMergeRegenerationDispatcher(
        workflow=recorder,
        selector=selector,
        summary_cache=cache,
        generator_diff_capturer=capturer or _FakeCapturer(),
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
    selector = _FakeSelector(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # Flag off reproduces the prior blanket path exactly, without consulting the selector.
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
    assert selector.calls == 0


async def test_missing_key_submits_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())

    await _dispatcher(selector, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=None
    )

    assert _full_regen_submitted(recorder)
    assert selector.calls == 0


async def test_cache_miss_submits_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())  # never seeded

    await _dispatcher(selector, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert _full_regen_submitted(recorder)
    assert selector.calls == 0


async def test_malformed_summary_submits_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_one_of_each())
    memory = MemoryCache()
    memory.storage[f"branch_merge:diff_id:{DIFF_ID}:diff_summary"] = "{not-valid-json"
    cache = _summary_cache(memory)

    await _dispatcher(selector, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert _full_regen_submitted(recorder)
    assert selector.calls == 0
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []


async def test_empty_plan_dispatches_nothing() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=SelectiveRegenerationPlan(generator_runs=[], artifact_generates=[]))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert recorder.submit_calls == []


async def test_selection_failure_falls_back_to_full_regeneration() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(error=RuntimeError("boom"))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert selector.calls == 1
    assert _full_regen_submitted(recorder)
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []


def _targeted_artifact() -> RequestArtifactDefinitionGenerate:
    return RequestArtifactDefinitionGenerate(
        branch=TARGET_BRANCH, artifact_definition_id="ad2", artifact_definition_name="targeted-art"
    )


async def test_merge_targets_artifacts_from_generator_output() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_one_of_each(), artifact_plan=[_targeted_artifact()])
    capturer = _FakeCapturer(diff_summary=[{"kind": "TestDevice"}])
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder, capturer).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # The generator is awaited (not submitted), its output is captured, and the artifacts are selected
    # from that captured diff -- alongside the merge-diff artifact -- with no blanket regeneration.
    assert [call["workflow"] for call in recorder.execute_calls] == [REQUEST_GENERATOR_DEFINITION_RUN]
    assert recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_RUN) == []
    assert capturer.calls == 1
    assert capturer.definition_names == [["gen"]]
    assert selector.select_artifacts_diffs == [[{"kind": "TestDevice"}]]
    submitted = [
        call["parameters"]["model"].artifact_definition_name
        for call in recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
    ]
    assert submitted == ["art", "targeted-art"]
    assert recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []


async def test_awaits_every_generator_before_capturing_output() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_two_generators())
    capturer = _FakeCapturer(diff_summary=[{"kind": "TestDevice"}])
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder, capturer).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # Racing the tail would capture against a partially-mutated graph.
    assert capturer.calls == 1
    assert capturer.definition_names == [["gd1", "gd2"]]
    assert [(call["kind"], call["workflow"]) for call in recorder.calls] == [
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN),
        ("execute", REQUEST_GENERATOR_DEFINITION_RUN),
        ("submit", REQUEST_ARTIFACT_DEFINITION_GENERATE),
    ]


async def test_merge_without_generator_keeps_selective_artifacts() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_only_artifacts())
    capturer = _FakeCapturer()
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder, capturer).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    # No generator ran, so no output is captured and the artifact selection stays narrow.
    assert capturer.calls == 0
    assert len(recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)) == 1
    assert recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []
    assert recorder.execute_calls == []


async def test_generator_output_capture_failure_falls_back_to_blanket_artifacts() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_one_of_each())
    capturer = _FakeCapturer(error=RuntimeError("capture boom"))
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder, capturer).dispatch(
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
    selector = _FakeSelector(plan=_plan_with_two_generators())
    capturer = _FakeCapturer(diff_summary=[{"kind": "TestDevice"}])
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder, capturer).dispatch(
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
    assert capturer.calls == 0


async def test_merge_consolidates_artifacts_selected_by_both_diffs() -> None:
    recorder = WorkflowRecorder()
    plan = SelectiveRegenerationPlan(
        generator_runs=[_generator_run(definition_id="gd1")],
        artifact_generates=[
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art", members=["m1"]
            ),
            RequestArtifactDefinitionGenerate(
                branch=TARGET_BRANCH, artifact_definition_id="ad2", artifact_definition_name="art2"
            ),
        ],
    )
    generator_output = [
        RequestArtifactDefinitionGenerate(
            branch=TARGET_BRANCH, artifact_definition_id="ad1", artifact_definition_name="art", members=["m2"]
        ),
        RequestArtifactDefinitionGenerate(
            branch=TARGET_BRANCH, artifact_definition_id="ad2", artifact_definition_name="art2", members=["m3"]
        ),
    ]
    selector = _FakeSelector(plan=plan, artifact_plan=generator_output)
    capturer = _FakeCapturer(diff_summary=[{"kind": "TestDevice"}])
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder, capturer).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    submits = recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
    by_def = {call["parameters"]["model"].artifact_definition_id: call["parameters"]["model"] for call in submits}
    # One request per definition -- ad1, selected by both diffs, is not dispatched twice.
    assert len(submits) == 2
    # Member filters are unioned; an unfiltered (all-members) request wins.
    assert sorted(by_def["ad1"].members) == ["m1", "m2"]
    assert by_def["ad2"].members == []
