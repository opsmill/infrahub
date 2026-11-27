from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.core.constants import CheckType, InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import ValidationError
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
from tests.helpers.workflow_override import override_workflow

from .test_failed_artifact_retry import (
    COMPLETED_AT,
    SOURCE_BRANCH,
    ArtifactCheckWorkflow,
    ArtifactRetryTestBase,
    RetryDataset,
)

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.proposed_change.models import RequestArtifactDefinitionCheck
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

FOREIGN_CHECKS_MESSAGE = "The selected artifact checks no longer belong to this validator. Refresh the checks view."


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
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        other_validator = await self._additional_validator(
            db=db, dataset=dataset, proposed_change_id=history.proposed_change_id
        )
        check_id = history.check_ids[dataset.devices[0].id]
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

    async def test_one_failed_check_keeps_other_failures_for_the_next_bulk_retry(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        selected_target = dataset.devices[0].id
        selected_check = history.check_ids[selected_target]
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
            update={"validator_id": history.validator_id, "check_ids": [selected_check]}
        )
        context = self._make_context(admin_account, default_branch)
        workflow = ArtifactCheckWorkflow(client=client)
        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            await validate_artifacts_generation(model=model, context=context)

            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert [
                (call["parameters"]["model"].target_id, call["parameters"]["model"].check_id) for call in calls
            ] == [(selected_target, selected_check)]
            assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions | {
                selected_check: ValidatorConclusion.SUCCESS.value
            }
            await self._assert_validator(
                db=db,
                validator_id=history.validator_id,
                state=ValidatorState.COMPLETED,
                conclusion=ValidatorConclusion.FAILURE,
            )

            workflow.reset()
            await validate_artifacts_generation(
                model=self._request(dataset=dataset, proposed_change_id=history.proposed_change_id), context=context
            )
            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)

        assert sorted(call["parameters"]["model"].target_id for call in calls) == sorted(
            device.id for device in dataset.devices[1:3]
        )
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == dict.fromkeys(
            history.check_ids.values(), ValidatorConclusion.SUCCESS.value
        )
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.SUCCESS,
        )

    async def test_check_identity_selects_a_target_without_an_artifact(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
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
                db=db,
                dataset=replace(
                    dataset, devices=(target, *dataset.devices), artifact_ids=(None, *dataset.artifact_ids)
                ),
            )
            check_id = history.check_ids[target.id]
            model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
                update={"validator_id": history.validator_id, "check_ids": [check_id]}
            )
            workflow = ArtifactCheckWorkflow(client=client)
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
            assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions | {
                check_id: ValidatorConclusion.SUCCESS.value
            }
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
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        other = await self._history(db=db, dataset=dataset)
        context = self._make_context(admin_account, default_branch)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        with pytest.raises(
            ValidationError, match=r"^The artifact validator does not belong to this proposed change\.$"
        ):
            await refresh_artifacts(
                model=self._refresh_request(model.model_copy(update={"validator_id": other.validator_id})),
                context=context,
            )
        assert workflow_recorder.submit_calls == []

        foreign_check = other.check_ids[dataset.devices[0].id]
        with pytest.raises(ValidationError, match=rf"^{re.escape(FOREIGN_CHECKS_MESSAGE)}$"):
            await validate_artifacts_generation(
                model=model.model_copy(update={"validator_id": history.validator_id, "check_ids": [foreign_check]}),
                context=context,
            )
        assert workflow_recorder.execute_calls == []
        await self._assert_history_unchanged(db=db, history=history)
        await self._assert_history_unchanged(db=db, history=other)

        moved_check_id = history.check_ids[dataset.devices[0].id]
        moved_check = await NodeManager.get_one(
            db=db, id=moved_check_id, kind=InfrahubKind.ARTIFACTCHECK, raise_on_error=True
        )
        await moved_check.validator.update(db=db, data=other.validator_id)
        await moved_check.validator.save(db=db)
        try:
            for retry_failed_only in (True, False):
                with pytest.raises(ValidationError, match=rf"^{re.escape(FOREIGN_CHECKS_MESSAGE)}$"):
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

    async def test_change_run_check_scope_renders_requested_targets_that_changed(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        requested_targets = (dataset.devices[0].id, dataset.devices[3].id)
        model = self._request(
            dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False
        ).model_copy(
            update={
                "validator_id": history.validator_id,
                "check_ids": [history.check_ids[target_id] for target_id in requested_targets],
            }
        )
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)
        workflow = ArtifactCheckWorkflow(client=client)
        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))

        calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert [call["parameters"]["model"].target_id for call in calls] == [dataset.devices[3].id]
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.FAILURE,
        )

    async def test_failed_retry_check_scope_does_not_render_a_successful_check(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
            update={"validator_id": history.validator_id, "check_ids": [history.check_ids[dataset.devices[-1].id]]}
        )

        await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))

        assert workflow_recorder.execute_calls == []
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.FAILURE,
        )

    async def test_passed_validator_still_validates_the_check_scope(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, failed=False)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
            update={"validator_id": history.validator_id, "check_ids": [history.check_ids[dataset.devices[0].id]]}
        )
        context = self._make_context(admin_account, default_branch)
        with pytest.raises(ValidationError, match=rf"^{re.escape(FOREIGN_CHECKS_MESSAGE)}$"):
            await validate_artifacts_generation(
                model=model.model_copy(update={"check_ids": [str(uuid4())]}), context=context
            )

        await validate_artifacts_generation(model=model, context=context)

        assert workflow_recorder.execute_calls == []
        await self._assert_history_unchanged(db=db, history=history)

    async def test_scoped_retry_keeps_the_failure_of_an_unselected_target_that_left_the_group(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        selected_target = dataset.devices[0].id
        removed_target = dataset.devices[1].id
        check_id = history.check_ids[selected_target]
        group = await NodeManager.get_one(
            db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
        )
        await group.members.update(db=db, data=[device.id for device in dataset.devices if device.id != removed_target])
        await group.members.save(db=db)
        try:
            model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id).model_copy(
                update={"validator_id": history.validator_id, "check_ids": [check_id]}
            )
            workflow = ArtifactCheckWorkflow(client=client)
            with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
                await validate_artifacts_generation(
                    model=model, context=self._make_context(admin_account, default_branch)
                )

            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert [call["parameters"]["model"].target_id for call in calls] == [selected_target]
            assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions | {
                check_id: ValidatorConclusion.SUCCESS.value
            }
            await self._assert_validator(
                db=db,
                validator_id=history.validator_id,
                state=ValidatorState.COMPLETED,
                conclusion=ValidatorConclusion.FAILURE,
            )
        finally:
            restored_group = await NodeManager.get_one(
                db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
            )
            await restored_group.members.update(db=db, data=[device.id for device in dataset.devices])
            await restored_group.members.save(db=db)
