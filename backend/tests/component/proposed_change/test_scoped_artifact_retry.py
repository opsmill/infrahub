from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from infrahub_sdk.protocols import CoreArtifactCheck

from infrahub.artifacts.models import ArtifactCheckResult, CheckArtifactCreate
from infrahub.core.constants import CheckType, InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import ValidationError
from infrahub.proposed_change.artifact_retry import ArtifactRetryRecord, ArtifactRetryRecords
from infrahub.proposed_change.models import RequestProposedChangePipeline, RequestProposedChangeRefreshArtifacts
from infrahub.proposed_change.tasks import (
    refresh_artifacts,
    run_proposed_change_pipeline,
    validate_artifacts_generation,
)
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
    REQUEST_ARTIFACT_DEFINITION_CHECK,
    REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
)
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.workflow_override import override_workflow

from .test_failed_artifact_retry import COMPLETED_AT, SOURCE_BRANCH, ArtifactRetryTestBase, RetryDataset

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.proposed_change.models import RequestArtifactDefinitionCheck
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition
    from tests.adapters.cache import MemoryCache


class SuccessfulArtifactWorkflow(WorkflowRecorder):
    def __init__(self, client: InfrahubClient) -> None:
        super().__init__()
        self.client = client

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
        assert parameters is not None
        model = parameters["model"]
        assert isinstance(model, CheckArtifactCreate)
        assert model.check_id is not None
        check = await self.client.get(kind=CoreArtifactCheck, id=model.check_id)
        check.conclusion.value = ValidatorConclusion.SUCCESS.value
        check.message.value = "Artifact rendered successfully"
        check.severity.value = "info"
        await check.save()
        return ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS, check_id=check.id)


class TestScopedArtifactRetry(ArtifactRetryTestBase):
    def _refresh_request(self, model: RequestArtifactDefinitionCheck) -> RequestProposedChangeRefreshArtifacts:
        return RequestProposedChangeRefreshArtifacts(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=model.branch_diff,
            retry_failed_only=model.retry_failed_only,
            validator_id=model.validator_id,
            check_ids=model.check_ids,
        )

    async def _additional_validator(
        self, *, db: InfrahubDatabase, dataset: RetryDataset, proposed_change_id: str
    ) -> Node:
        definition = await NodeManager.get_one(
            db=db,
            id=dataset.definition.definition_id,
            kind=InfrahubKind.ARTIFACTDEFINITION,
            branch=SOURCE_BRANCH,
            raise_on_error=True,
        )
        transform = await definition.transformation.get_peer(db=db)
        other_definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION, branch=SOURCE_BRANCH)
        await other_definition.new(
            db=db,
            name=f"other-scoped-definition-{uuid4()}",
            artifact_name="other-config",
            targets=dataset.group_id,
            transformation=transform.id,
            content_type="text/plain",
            parameters={"value": {"name": "name__value"}},
        )
        await other_definition.save(db=db)
        validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
        await validator.new(
            db=db,
            definition=other_definition,
            proposed_change=proposed_change_id,
            state=ValidatorState.COMPLETED.value,
            conclusion=ValidatorConclusion.FAILURE.value,
            completed_at=COMPLETED_AT,
        )
        await validator.save(db=db)
        return validator

    async def test_pipeline_keeps_validator_scope_through_refresh_fanout(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        other_validator = await self._additional_validator(
            db=db, dataset=dataset, proposed_change_id=history.proposed_change_id
        )
        check_id = history.outcomes[dataset.devices[0].id].check_id
        assert check_id is not None
        context = self._make_context(admin_account, default_branch)
        await run_proposed_change_pipeline(
            model=RequestProposedChangePipeline(
                proposed_change=history.proposed_change_id,
                source_branch=SOURCE_BRANCH,
                source_branch_sync_with_git=True,
                destination_branch=default_branch.name,
                check_type=CheckType.ARTIFACT,
                retry_failed_only=True,
                validator_id=history.validator_id,
                check_ids=[check_id],
            ),
            context=context,
        )

        refresh_calls = workflow_recorder.get_submit_calls_for(REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS)
        assert len(refresh_calls) == 1
        refresh_request = refresh_calls[0]["parameters"]["model"]
        assert refresh_request.validator_id == history.validator_id
        assert refresh_request.check_ids == [check_id]
        await refresh_artifacts(model=refresh_request, context=context)

        calls = workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        assert len(calls) == 1
        request = calls[0]["parameters"]["model"]
        assert request.artifact_definition.definition_id == dataset.definition.definition_id
        assert request.validator_id == history.validator_id
        assert request.check_ids == [check_id]
        assert request.retry_failed_only is True
        untouched = await NodeManager.get_one(db=db, id=other_validator.id, kind=InfrahubKind.ARTIFACTVALIDATOR)
        assert untouched is not None
        assert untouched.conclusion.value.value == ValidatorConclusion.FAILURE.value
        assert untouched.completed_at.value == COMPLETED_AT
        await self._assert_history_unchanged(db=db, history=history)

    async def test_one_failed_check_preserves_other_failures_for_the_next_bulk_retry(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        selected_target = dataset.devices[0].id
        selected_check = history.outcomes[selected_target].check_id
        assert selected_check is not None
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
            update={"validator_id": history.validator_id, "check_ids": [selected_check]}
        )
        context = self._make_context(admin_account, default_branch)
        records = ArtifactRetryRecords(memory_cache)
        workflow = SuccessfulArtifactWorkflow(client=client)
        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            await validate_artifacts_generation(model=model, context=context)

            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert [call["parameters"]["model"].target_id for call in calls] == [selected_target]
            assert calls[0]["parameters"]["model"].check_id == selected_check
            record = await records.get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            assert record is not None
            remaining_failures = {device.id for device in dataset.devices[1:3]}
            assert record.failed_target_ids == remaining_failures
            assert {target: outcome for target, outcome in record.outcomes.items() if target != selected_target} == {
                target: outcome for target, outcome in history.outcomes.items() if target != selected_target
            }
            validator = await NodeManager.get_one(db=db, id=history.validator_id, kind=InfrahubKind.ARTIFACTVALIDATOR)
            assert validator is not None
            assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
            checks = await NodeManager.query(
                db=db, schema=InfrahubKind.ARTIFACTCHECK, filters={"validator__ids": [history.validator_id]}
            )
            assert {check.id: check.conclusion.value.value for check in checks} == {
                outcome.check_id: ValidatorConclusion.SUCCESS.value
                if target_id == selected_target
                else outcome.conclusion.value
                for target_id, outcome in history.outcomes.items()
            }

            workflow.reset()
            await validate_artifacts_generation(
                model=self._request(dataset=dataset, proposed_change_id=history.proposed_change_id), context=context
            )

        calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert {call["parameters"]["model"].target_id for call in calls} == remaining_failures
        assert len(calls) == 2
        record = await records.get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.failed_target_ids == frozenset()
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind=InfrahubKind.ARTIFACTVALIDATOR)
        assert validator is not None
        assert validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        checks = await NodeManager.query(
            db=db, schema=InfrahubKind.ARTIFACTCHECK, filters={"validator__ids": [history.validator_id]}
        )
        assert {check.id for check in checks} == {outcome.check_id for outcome in history.outcomes.values()}
        assert all(check.conclusion.value.value == ValidatorConclusion.SUCCESS.value for check in checks)

    async def test_check_identity_selects_a_target_without_an_artifact(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        target = await Node.init(db=db, schema="TestRetryDevice", branch=SOURCE_BRANCH)
        await target.new(db=db, name=f"without-artifact-{uuid4()}", color="blue")
        await target.save(db=db)
        group = await NodeManager.get_one(
            db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
        )
        await group.members.update(db=db, data=[*(device.id for device in dataset.devices), target.id])
        await group.members.save(db=db)
        try:
            history = await self._history(
                db=db, dataset=replace(dataset, devices=(target, *dataset.devices)), memory_cache=memory_cache
            )
            check_id = history.outcomes[target.id].check_id
            assert check_id is not None
            model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
                update={"validator_id": history.validator_id, "check_ids": [check_id]}
            )
            workflow = SuccessfulArtifactWorkflow(client=client)
            with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
                await validate_artifacts_generation(
                    model=model, context=self._make_context(admin_account, default_branch)
                )

            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert len(calls) == 1
            request = calls[0]["parameters"]["model"]
            assert request.target_id == target.id
            assert request.artifact_id is None
            assert request.check_id == check_id
            record = await ArtifactRetryRecords(memory_cache).get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            assert record is not None
            assert record.outcomes[target.id] == ArtifactCheckResult(
                conclusion=ValidatorConclusion.SUCCESS, check_id=check_id
            )
        finally:
            restored_group = await NodeManager.get_one(
                db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
            )
            await restored_group.members.update(db=db, data=[device.id for device in dataset.devices])
            await restored_group.members.save(db=db)
            await target.delete(db=db)

    async def test_validator_and_check_scopes_cannot_cross_proposed_changes(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        other = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        context = self._make_context(admin_account, default_branch)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        with pytest.raises(ValidationError):
            await refresh_artifacts(
                model=self._refresh_request(model.model_copy(update={"validator_id": other.validator_id})),
                context=context,
            )
        assert workflow_recorder.submit_calls == []

        foreign_check = other.outcomes[dataset.devices[0].id].check_id
        assert foreign_check is not None
        with pytest.raises(ValidationError):
            await validate_artifacts_generation(
                model=model.model_copy(update={"validator_id": history.validator_id, "check_ids": [foreign_check]}),
                context=context,
            )
        assert workflow_recorder.execute_calls == []
        await self._assert_history_unchanged(db=db, history=history)
        await self._assert_history_unchanged(db=db, history=other)

        moved_check_id = history.outcomes[dataset.devices[0].id].check_id
        assert moved_check_id is not None
        records = ArtifactRetryRecords(memory_cache)
        previous_record = await records.get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        moved_check = await NodeManager.get_one(
            db=db, id=moved_check_id, kind=InfrahubKind.ARTIFACTCHECK, raise_on_error=True
        )
        await moved_check.validator.update(db=db, data=other.validator_id)
        await moved_check.validator.save(db=db)
        try:
            for retry_failed_only in (True, False):
                with pytest.raises(ValidationError):
                    await validate_artifacts_generation(
                        model=model.model_copy(
                            update={
                                "validator_id": history.validator_id,
                                "check_ids": [moved_check_id],
                                "retry_failed_only": retry_failed_only,
                            }
                        ),
                        context=context,
                    )
                assert workflow_recorder.execute_calls == []
                assert (
                    await records.get(
                        proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
                    )
                    == previous_record
                )
                validator = await NodeManager.get_one(
                    db=db, id=history.validator_id, kind=InfrahubKind.ARTIFACTVALIDATOR, raise_on_error=True
                )
                assert validator.state.value.value == ValidatorState.COMPLETED.value
                assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
                assert validator.completed_at.value == COMPLETED_AT
        finally:
            restored_check = await NodeManager.get_one(
                db=db, id=moved_check_id, kind=InfrahubKind.ARTIFACTCHECK, raise_on_error=True
            )
            await restored_check.validator.update(db=db, data=history.validator_id)
            await restored_check.validator.save(db=db)
        await self._assert_history_unchanged(db=db, history=history)
        await self._assert_history_unchanged(db=db, history=other)

    async def test_missing_or_stale_check_history_never_broadens_an_explicit_scope(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache, save_history=False)
        check_id = history.outcomes[dataset.devices[0].id].check_id
        assert check_id is not None
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
            update={"validator_id": history.validator_id, "check_ids": [check_id]}
        )
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)
        records = ArtifactRetryRecords(memory_cache)
        for stale in (False, True):
            if stale:
                await records.complete(
                    proposed_change_id=history.proposed_change_id,
                    definition_id=dataset.definition.definition_id,
                    record=ArtifactRetryRecord(validator_id=history.validator_id),
                    completed_at="2025-01-01T11:00:00Z",
                    outcomes=history.outcomes,
                )
            for retry_failed_only in (True, False):
                with pytest.raises(ValidationError):
                    await validate_artifacts_generation(
                        model=model.model_copy(update={"retry_failed_only": retry_failed_only}),
                        context=self._make_context(admin_account, default_branch),
                    )
                assert workflow_recorder.execute_calls == []
                await self._assert_history_unchanged(db=db, history=history)

    async def test_ordinary_check_scope_intersects_incremental_selection(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        requested_targets = (dataset.devices[0].id, dataset.devices[3].id)
        check_ids = [history.outcomes[target_id].check_id for target_id in requested_targets]
        assert all(check_ids)
        model = self._request(
            dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False
        ).model_copy(update={"validator_id": history.validator_id, "check_ids": check_ids})
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)
        workflow = SuccessfulArtifactWorkflow(client=client)
        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))

        calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert [call["parameters"]["model"].target_id for call in calls] == [dataset.devices[3].id]
        record = await ArtifactRetryRecords(memory_cache).get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.failed_target_ids == {device.id for device in dataset.devices[:3]}
        assert record.outcomes == history.outcomes
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind=InfrahubKind.ARTIFACTVALIDATOR)
        assert validator is not None
        assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value

    async def test_strict_check_scope_does_not_rerun_a_successful_check(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        check_id = history.outcomes[dataset.devices[-1].id].check_id
        assert check_id is not None
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
            update={"validator_id": history.validator_id, "check_ids": [check_id]}
        )
        await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))

        assert workflow_recorder.execute_calls == []
        record = await ArtifactRetryRecords(memory_cache).get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.outcomes == history.outcomes
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind=InfrahubKind.ARTIFACTVALIDATOR)
        assert validator is not None
        assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value

    async def test_successful_validator_still_validates_explicit_check_scope(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(
            db=db, dataset=dataset, memory_cache=memory_cache, failed=False, save_history=False
        )
        check_id = history.outcomes[dataset.devices[0].id].check_id
        assert check_id is not None
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
            update={"validator_id": history.validator_id, "check_ids": [check_id]}
        )
        context = self._make_context(admin_account, default_branch)
        with pytest.raises(ValidationError):
            await validate_artifacts_generation(model=model, context=context)

        records = ArtifactRetryRecords(memory_cache)
        await records.complete(
            proposed_change_id=history.proposed_change_id,
            definition_id=dataset.definition.definition_id,
            record=ArtifactRetryRecord(validator_id=history.validator_id),
            completed_at=COMPLETED_AT,
            outcomes=history.outcomes,
        )
        before = await records.get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        with pytest.raises(ValidationError):
            await validate_artifacts_generation(
                model=model.model_copy(update={"check_ids": [str(uuid4())]}), context=context
            )

        await validate_artifacts_generation(model=model, context=context)

        assert workflow_recorder.execute_calls == []
        assert (
            await records.get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            == before
        )
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind=InfrahubKind.ARTIFACTVALIDATOR)
        assert validator is not None
        assert validator.state.value.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        assert validator.completed_at.value == COMPLETED_AT

    async def test_scoped_retry_preserves_an_unselected_failed_target_that_left_the_group(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        selected_target = dataset.devices[0].id
        removed_target = dataset.devices[1].id
        check_id = history.outcomes[selected_target].check_id
        assert check_id is not None
        group = await NodeManager.get_one(
            db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
        )
        await group.members.update(db=db, data=[device.id for device in dataset.devices if device.id != removed_target])
        await group.members.save(db=db)
        try:
            model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
                update={"validator_id": history.validator_id, "check_ids": [check_id]}
            )
            workflow = SuccessfulArtifactWorkflow(client=client)
            with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
                await validate_artifacts_generation(
                    model=model, context=self._make_context(admin_account, default_branch)
                )

            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert [call["parameters"]["model"].target_id for call in calls] == [selected_target]
            record = await ArtifactRetryRecords(memory_cache).get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            assert record is not None
            assert record.outcomes[removed_target] == history.outcomes[removed_target]
            assert record.failed_target_ids == {device.id for device in dataset.devices[1:3]}
            removed_check = await NodeManager.get_one(
                db=db, id=history.outcomes[removed_target].check_id, kind=InfrahubKind.ARTIFACTCHECK
            )
            assert removed_check is not None
            assert removed_check.conclusion.value.value == ValidatorConclusion.FAILURE.value
        finally:
            restored_group = await NodeManager.get_one(
                db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
            )
            await restored_group.members.update(db=db, data=[device.id for device in dataset.devices])
            await restored_group.members.save(db=db)
