from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.regeneration_dispatcher import PostMergeRegenerationDispatcher
from infrahub.core.merge.selective_regen.models import SelectiveRegenerationPlan
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

DIFF_ID = "diff-1"
TARGET_BRANCH = "main"


def _summary_cache(cache: MemoryCache) -> DiffSummaryCache:
    return DiffSummaryCache(cache=cache, serializer=DiffSummarySerializer(), key_namespace="branch_merge")


class _FakeSelector:
    """A RegenerationSelector that returns a canned plan or raises, recording its invocations."""

    def __init__(self, *, plan: SelectiveRegenerationPlan | None = None, error: Exception | None = None) -> None:
        self._plan = plan
        self._error = error
        self.calls = 0

    async def build_plan(self, diff_summary: list, target_branch: str) -> SelectiveRegenerationPlan:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return (
            self._plan
            if self._plan is not None
            else SelectiveRegenerationPlan(generator_runs=[], artifact_generates=[])
        )


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


def _dispatcher(
    selector: _FakeSelector, cache: DiffSummaryCache, recorder: WorkflowRecorder
) -> PostMergeRegenerationDispatcher:
    return PostMergeRegenerationDispatcher(
        workflow=recorder, selector=selector, summary_cache=cache, log=logging.getLogger("test")
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

    assert _full_regen_submitted(recorder)
    assert recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []
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


async def test_selected_definitions_are_dispatched() -> None:
    recorder = WorkflowRecorder()
    selector = _FakeSelector(plan=_plan_with_one_of_each())
    cache = _summary_cache(MemoryCache())
    await cache.set(diff_id=DIFF_ID, diff_summary=[])

    await _dispatcher(selector, cache, recorder).dispatch(
        context=_context(), target_branch=TARGET_BRANCH, merge_diff_cache_key=DIFF_ID
    )

    assert len(recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_RUN)) == 1
    assert len(recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)) == 1
    assert recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []
    assert recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN) == []


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
