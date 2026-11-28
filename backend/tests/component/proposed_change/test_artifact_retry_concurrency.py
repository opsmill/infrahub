from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import lock
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.proposed_change.tasks import validate_artifacts_generation
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE
from tests.adapters.lock import LockAction, LockTimeline, install_recording_lock_registry
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.workflow_override import override_workflow

from .test_failed_artifact_retry import ArtifactRetryTestBase, RetryDataset

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from fast_depends import Provider

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition

WAIT_TIMEOUT_SECONDS = 30
FIRST_TARGET_FINISHED = "first target finished"


class NotifyingLockTimeline(LockTimeline):
    """A lock timeline that a test can wait on until a condition over its events holds."""

    def __init__(self) -> None:
        super().__init__()
        self._recorded = asyncio.Event()

    def record(self, name: str, action: LockAction, label: str | None = None) -> int:
        seq = super().record(name=name, action=action, label=label)
        self._recorded.set()
        return seq

    async def wait_until(self, condition: Callable[[], bool]) -> None:
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            while not condition():
                self._recorded.clear()
                await self._recorded.wait()


class BlockedArtifactWorkflow(WorkflowRecorder):
    def __init__(self, first_run_target_count: int, timeline: LockTimeline) -> None:
        super().__init__()
        self.first_run_target_count = first_run_target_count
        self.timeline = timeline
        self.first_run_started = asyncio.Event()
        self.release_first_target = asyncio.Event()
        self.first_target_cancelled = False

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> Any:
        result = await super().execute_workflow(
            workflow=workflow,
            expected_return=expected_return,
            context=context,
            parameters=parameters,
            tags=tags,
            priority=priority,
        )
        if workflow != GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE:
            return result
        calls = self.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        call_number = len(calls)
        if call_number == self.first_run_target_count:
            self.first_run_started.set()
        if call_number == 1:
            try:
                await asyncio.wait_for(self.release_first_target.wait(), timeout=WAIT_TIMEOUT_SECONDS)
            except asyncio.CancelledError:
                self.first_target_cancelled = True
                raise
            self.timeline.checkpoint(FIRST_TARGET_FINISHED)
        assert parameters is not None
        assert isinstance(parameters["model"], CheckArtifactCreate)
        if call_number <= self.first_run_target_count:
            return ValidatorConclusion.FAILURE
        return ValidatorConclusion.SUCCESS


@pytest.fixture
def lock_timeline() -> Generator[NotifyingLockTimeline, None, None]:
    original = lock.registry
    timeline = NotifyingLockTimeline()
    install_recording_lock_registry(timeline=timeline)
    try:
        yield timeline
    finally:
        lock.registry = original


class TestArtifactRetryConcurrency(ArtifactRetryTestBase):
    async def test_cancelled_validation_drains_children_before_a_new_run_can_write(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
        lock_timeline: NotifyingLockTimeline,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        context = self._make_context(admin_account, default_branch)
        workflow = BlockedArtifactWorkflow(first_run_target_count=3, timeline=lock_timeline)
        lock_name = lock.registry.get(
            name=f"{history.proposed_change_id}:{dataset.definition.definition_id}", namespace="artifact-validation"
        ).name

        def lock_actions() -> list[LockAction]:
            return [event.action for event in lock_timeline.events if event.name == lock_name]

        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            first = asyncio.create_task(validate_artifacts_generation(model=model, context=context))
            second: asyncio.Task[None] | None = None
            try:
                await asyncio.wait_for(workflow.first_run_started.wait(), timeout=WAIT_TIMEOUT_SECONDS)
                first.cancel()
                second = asyncio.create_task(validate_artifacts_generation(model=model, context=context))
                await lock_timeline.wait_until(lambda: lock_timeline.waiting(lock_name) == 1)

                assert not first.done()
                assert lock_actions() == [LockAction.WAIT, LockAction.ACQUIRE, LockAction.WAIT]
                assert len(workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)) == 3

                assert first.cancel()
                cancellation_scheduled = asyncio.Event()
                asyncio.get_running_loop().call_soon(cancellation_scheduled.set)
                await asyncio.wait_for(cancellation_scheduled.wait(), timeout=WAIT_TIMEOUT_SECONDS)
                assert not first.done()
                assert lock_actions() == [LockAction.WAIT, LockAction.ACQUIRE, LockAction.WAIT]
                assert not workflow.first_target_cancelled
                assert len(workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)) == 3

                workflow.release_first_target.set()
                with pytest.raises(asyncio.CancelledError, match=r"^$"):
                    await asyncio.wait_for(first, timeout=WAIT_TIMEOUT_SECONDS)
                await asyncio.wait_for(second, timeout=WAIT_TIMEOUT_SECONDS)
            finally:
                workflow.release_first_target.set()
                running = [task for task in (first, second) if task is not None]
                for task in running:
                    if not task.done():
                        task.cancel()
                await asyncio.wait_for(asyncio.gather(*running, return_exceptions=True), timeout=WAIT_TIMEOUT_SECONDS)

        assert lock_actions() == [
            LockAction.WAIT,
            LockAction.ACQUIRE,
            LockAction.WAIT,
            LockAction.RELEASE,
            LockAction.ACQUIRE,
            LockAction.RELEASE,
        ]
        second_acquired = [
            event.seq
            for event in lock_timeline.events
            if event.name == lock_name and event.action == LockAction.ACQUIRE
        ][1]
        assert lock_timeline.checkpoint_seqs(FIRST_TARGET_FINISHED)[0] < second_acquired
        assert not workflow.first_target_cancelled
        calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(calls) == 6
        assert sorted(call["parameters"]["model"].target_id for call in calls[3:]) == sorted(
            device.id for device in dataset.devices[:3]
        )
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.SUCCESS,
        )
