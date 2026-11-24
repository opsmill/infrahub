from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from infrahub_sdk.protocols import CoreArtifactValidator

from infrahub import lock
from infrahub.artifacts.models import ArtifactCheckResult, CheckArtifactCreate
from infrahub.core.constants import ValidatorConclusion
from infrahub.proposed_change.artifact_retry import ArtifactRetryRecord, ArtifactRetryRecords
from infrahub.proposed_change.tasks import validate_artifacts_generation
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.workflow_override import override_workflow

from .test_failed_artifact_retry import ArtifactRetryTestBase, RetryDataset

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition
    from tests.adapters.cache import MemoryCache

WAIT_TIMEOUT_SECONDS = 30


class BlockedArtifactWorkflow(WorkflowRecorder):
    def __init__(self, first_run_target_count: int) -> None:
        super().__init__()
        self.first_run_target_count = first_run_target_count
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
        assert parameters is not None
        model = parameters["model"]
        assert isinstance(model, CheckArtifactCreate)
        return ArtifactCheckResult(
            conclusion=ValidatorConclusion.FAILURE
            if call_number <= self.first_run_target_count
            else ValidatorConclusion.SUCCESS,
            check_id=model.check_id,
        )


class TestArtifactRetryConcurrency(ArtifactRetryTestBase):
    async def test_cancelled_validation_drains_children_before_a_new_run_can_write(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        dependency_provider: Provider,
        client: InfrahubClient,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        first_model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        second_model = self._request(
            dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False
        )
        context = self._make_context(admin_account, default_branch)
        records = ArtifactRetryRecords(cache=memory_cache)
        workflow = BlockedArtifactWorkflow(first_run_target_count=3)
        validation_lock = lock.registry.get(
            name=f"{history.proposed_change_id}:{dataset.definition.definition_id}", namespace="artifact-validation"
        )
        acquire = validation_lock.acquire
        acquisition_count = 0
        second_attempted = asyncio.Event()
        second_acquired = asyncio.Event()
        records_before_second_run: list[ArtifactRetryRecord | None] = []

        async def observed_acquire() -> None:
            nonlocal acquisition_count
            acquisition_count += 1
            second_run = acquisition_count == 2
            if second_run:
                second_attempted.set()
            await acquire()
            if second_run:
                records_before_second_run.append(
                    await records.get(
                        proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
                    )
                )
                second_acquired.set()

        with (
            override_workflow(workflow=workflow, dependency_provider=dependency_provider),
            patch.object(validation_lock, "acquire", new=observed_acquire),
        ):
            first = asyncio.create_task(validate_artifacts_generation(model=first_model, context=context))
            second: asyncio.Task[None] | None = None
            try:
                await asyncio.wait_for(workflow.first_run_started.wait(), timeout=WAIT_TIMEOUT_SECONDS)
                first.cancel()
                second = asyncio.create_task(validate_artifacts_generation(model=second_model, context=context))
                await asyncio.wait_for(second_attempted.wait(), timeout=WAIT_TIMEOUT_SECONDS)

                assert not first.done()
                assert not second_acquired.is_set()
                assert len(workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)) == 3

                assert first.cancel()
                cancellation_scheduled = asyncio.Event()
                asyncio.get_running_loop().call_soon(cancellation_scheduled.set)
                await asyncio.wait_for(cancellation_scheduled.wait(), timeout=WAIT_TIMEOUT_SECONDS)
                assert not first.done()
                assert not second_acquired.is_set()
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

        assert len(records_before_second_run) == 1
        interrupted = records_before_second_run[0]
        assert interrupted is not None
        assert interrupted.completed is False
        assert interrupted.completed_at is None
        assert not workflow.first_target_cancelled
        calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(calls) == 9
        assert {call["parameters"]["model"].target_id for call in calls[3:]} == {
            device.id for device in dataset.devices
        }
        completed = await records.get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert completed is not None
        assert completed.failed_target_ids == frozenset()
        assert set(completed.outcomes) == {device.id for device in dataset.devices}
        validator = await client.get(kind=CoreArtifactValidator, id=history.validator_id)
        assert completed.matches_validator(
            validator_id=validator.id,
            completed_at=validator.completed_at.value,
            conclusion=validator.conclusion.value,
            state=validator.state.value,
        )
