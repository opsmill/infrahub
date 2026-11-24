from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from infrahub.artifacts.models import ArtifactCheckResult
from infrahub.core.constants import (
    CheckType,
    InfrahubKind,
    RepositoryInternalStatus,
    ValidatorConclusion,
    ValidatorState,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.exceptions import ResourceNotFoundError, ValidationError, WorkflowOrchestrationError
from infrahub.message_bus.types import (
    ProposedChangeArtifactDefinition,
    ProposedChangeBranchDiff,
    ProposedChangeRepository,
)
from infrahub.proposed_change.artifact_retry import ArtifactRetryRecord, ArtifactRetryRecords
from infrahub.proposed_change.branch_diff import get_diff_summary_cache, set_diff_summary_cache
from infrahub.proposed_change.models import (
    RequestArtifactDefinitionCheck,
    RequestProposedChangePipeline,
    RequestProposedChangeRefreshArtifacts,
)
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
from tests.helpers.schema import load_schema

from .conftest import ArtifactRegenTestBase, make_node_diff

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.artifacts.models import CheckArtifactCreate
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

SOURCE_BRANCH = "feature/failed-artifact-retry"
COMPLETED_AT = "2025-01-01T12:00:00Z"
QUERY = """
query RetryDevices($ids: [ID!]!) {
    TestRetryDevice(ids: $ids) {
        edges { node { name { value } color { value } } }
    }
}
"""
ARTIFACT_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="RetryDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="color", kind="Text")],
        )
    ]
)


@dataclass(frozen=True)
class RetryDataset:
    devices: tuple[Node, ...]
    group_id: str
    repository: ProposedChangeRepository
    definition: ProposedChangeArtifactDefinition


@dataclass(frozen=True)
class RetryHistory:
    proposed_change_id: str
    validator_id: str
    outcomes: dict[str, ArtifactCheckResult]


class ArtifactRetryTestBase(ArtifactRegenTestBase):
    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> RetryDataset:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)
        devices = []
        for name in ("failed-1", "failed-2", "failed-3", "changed-success-1", "changed-success-2", "success"):
            device = await Node.init(db=db, schema="TestRetryDevice")
            await device.new(db=db, name=name, color="blue")
            await device.save(db=db)
            devices.append(device)

        repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repository.new(db=db, name="retry-artifacts", location="https://github.com/test/retry-artifacts.git")
        await repository.save(db=db)
        query = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query.new(db=db, name="RetryDevices", query=QUERY, models=["TestRetryDevice"])
        await query.save(db=db)
        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await transform.new(
            db=db,
            name="retry-artifacts",
            query=query.id,
            repository=repository.id,
            template_path="device.j2",
            dependencies=["device.j2"],
            dependencies_complete=True,
        )
        await transform.save(db=db)
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="retry-artifact-targets", members=devices)
        await group.save(db=db)
        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name="retry-device-config",
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)
        source_branch = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)
        for device in devices:
            artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch)
            await artifact.new(
                db=db,
                name="device-config",
                status="Ready",
                content_type="text/plain",
                object=device,
                definition=definition,
                storage_id=str(uuid4()),
                checksum="already-rendered",
            )
            await artifact.save(db=db)
            query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP, branch=source_branch)
            await query_group.new(
                db=db, name=f"retry-query-{device.id}", query=query.id, members=[device], subscribers=[artifact]
            )
            await query_group.save(db=db)

        return RetryDataset(
            devices=tuple(devices),
            group_id=group.id,
            repository=ProposedChangeRepository(
                repository_id=repository.id,
                repository_name="retry-artifacts",
                read_only=False,
                source_branch=SOURCE_BRANCH,
                destination_branch=default_branch.name,
                internal_status=RepositoryInternalStatus.ACTIVE.value,
                source_commit="source-commit",
                destination_commit="destination-commit",
            ),
            definition=ProposedChangeArtifactDefinition(
                definition_id=definition.id,
                definition_name="retry-device-config",
                artifact_name="device-config",
                query_name="RetryDevices",
                query_id=query.id,
                query_payload=QUERY,
                repository_id=repository.id,
                transform_kind=InfrahubKind.TRANSFORMJINJA2,
                template_path="device.j2",
                content_type="text/plain",
                timeout=60,
            ),
        )

    async def _history(
        self,
        *,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        failed: bool = True,
        save_history: bool = True,
    ) -> RetryHistory:
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db,
            name=f"retry-{uuid4()}",
            source_branch=SOURCE_BRANCH,
            destination_branch=dataset.repository.destination_branch,
        )
        await proposed_change.save(db=db)
        validator = await Node.init(db=db, schema="CoreArtifactValidator")
        await validator.new(
            db=db,
            label="Artifact Validator: retry-device-config",
            definition=dataset.definition.definition_id,
            proposed_change=proposed_change,
            state=ValidatorState.COMPLETED.value,
            conclusion=ValidatorConclusion.FAILURE.value if failed else ValidatorConclusion.SUCCESS.value,
            started_at=COMPLETED_AT,
            completed_at=COMPLETED_AT,
        )
        await validator.save(db=db)
        outcomes = {}
        for index, device in enumerate(dataset.devices):
            conclusion = ValidatorConclusion.FAILURE if failed and index < 3 else ValidatorConclusion.SUCCESS
            check = await Node.init(db=db, schema="CoreArtifactCheck")
            await check.new(
                db=db,
                name=f"device-config: {device.name.value}",
                origin=dataset.repository.repository_id,
                kind="ArtifactDefinition",
                validator=validator,
                conclusion=conclusion.value,
                severity="critical" if conclusion == ValidatorConclusion.FAILURE else "info",
                message="Previous render result",
                created_at=COMPLETED_AT,
            )
            await check.save(db=db)
            outcomes[device.id] = ArtifactCheckResult(conclusion=conclusion, check_id=check.id)
        history = RetryHistory(proposed_change_id=proposed_change.id, validator_id=validator.id, outcomes=outcomes)
        if save_history:
            await ArtifactRetryRecords(memory_cache).complete(
                proposed_change_id=history.proposed_change_id,
                definition_id=dataset.definition.definition_id,
                record=ArtifactRetryRecord(validator_id=history.validator_id),
                completed_at=COMPLETED_AT,
                outcomes=outcomes,
            )
        return history

    def _request(
        self, *, dataset: RetryDataset, proposed_change_id: str, retry_failed_only: bool = True
    ) -> RequestArtifactDefinitionCheck:
        return RequestArtifactDefinitionCheck(
            artifact_definition=dataset.definition,
            branch_diff=ProposedChangeBranchDiff(pipeline_id=uuid4(), repositories=[dataset.repository]),
            proposed_change=proposed_change_id,
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=True,
            destination_branch=dataset.repository.destination_branch,
            retry_failed_only=retry_failed_only,
        )

    async def _set_changed_successes(
        self, *, dataset: RetryDataset, model: RequestArtifactDefinitionCheck, memory_cache: MemoryCache
    ) -> None:
        await set_diff_summary_cache(
            pipeline_id=model.branch_diff.pipeline_id,
            diff_summary=[
                make_node_diff(device.id, "TestRetryDevice", SOURCE_BRANCH, ["color"])
                for device in dataset.devices[3:5]
            ],
            cache=memory_cache,
        )

    async def _assert_history_unchanged(self, *, db: InfrahubDatabase, history: RetryHistory) -> None:
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
        assert validator.completed_at.value == COMPLETED_AT
        checks = await NodeManager.query(
            db=db, schema="CoreArtifactCheck", filters={"validator__ids": [history.validator_id]}
        )
        assert len(checks) == len(history.outcomes)
        assert {check.id: check.conclusion.value.value for check in checks} == {
            outcome.check_id: outcome.conclusion.value for outcome in history.outcomes.values()
        }


class TestFailedArtifactRetry(ArtifactRetryTestBase):
    async def test_retries_exactly_failed_targets_and_clears_retry_eligibility(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)
        context = self._make_context(admin_account, default_branch)

        await validate_artifacts_generation(model=model, context=context)

        calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(calls) == 3
        assert {call["parameters"]["model"].target_id: call["parameters"]["model"].check_id for call in calls} == {
            device.id: history.outcomes[device.id].check_id for device in dataset.devices[:3]
        }
        record = await ArtifactRetryRecords(memory_cache).get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.completed is True
        assert record.failed_target_ids == frozenset()
        assert set(record.outcomes) == {device.id for device in dataset.devices}
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value

        workflow_recorder.reset()
        await validate_artifacts_generation(model=model, context=context)
        assert workflow_recorder.execute_calls == []
        assert (
            await ArtifactRetryRecords(memory_cache).get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            == record
        )

    async def test_normal_incremental_run_preserves_unselected_failures(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False)
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)

        await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))

        calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(calls) == 2
        assert {call["parameters"]["model"].target_id for call in calls} == {
            device.id for device in dataset.devices[3:5]
        }
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
        record = await ArtifactRetryRecords(memory_cache).get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.failed_target_ids == {device.id for device in dataset.devices[:3]}
        assert {target_id: record.outcomes[target_id] for target_id in record.failed_target_ids} == {
            device.id: history.outcomes[device.id] for device in dataset.devices[:3]
        }
        failed_checks = await NodeManager.query(
            db=db,
            schema="CoreArtifactCheck",
            filters={"validator__ids": [history.validator_id], "conclusion__value": ValidatorConclusion.FAILURE.value},
        )
        assert len(failed_checks) == 3
        assert {check.id for check in failed_checks} == {
            history.outcomes[device.id].check_id for device in dataset.devices[:3]
        }

    async def test_missing_incomplete_or_stale_history_rejects_without_dispatch(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache, save_history=False)
        records = ArtifactRetryRecords(memory_cache)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)
        record = ArtifactRetryRecord(validator_id=history.validator_id, outcomes=history.outcomes)
        for history_state in ("missing", "incomplete", "stale"):
            if history_state == "incomplete":
                await records.start(
                    proposed_change_id=history.proposed_change_id,
                    definition_id=dataset.definition.definition_id,
                    record=record,
                )
            elif history_state == "stale":
                await records.complete(
                    proposed_change_id=history.proposed_change_id,
                    definition_id=dataset.definition.definition_id,
                    record=record,
                    completed_at="2025-01-01T11:00:00Z",
                    outcomes=history.outcomes,
                )
            with pytest.raises(ValidationError, match=re.escape("completed target history is missing or stale")):
                await validate_artifacts_generation(
                    model=model, context=self._make_context(admin_account, default_branch)
                )
            assert workflow_recorder.execute_calls == [], history_state
            await self._assert_history_unchanged(db=db, history=history)

    @pytest.mark.parametrize("history_failed", [True, False])
    async def test_ordinary_checks_rebuild_missing_history_before_strict_retry(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        monkeypatch: pytest.MonkeyPatch,
        history_failed: bool,
    ) -> None:
        history = await self._history(
            db=db, dataset=dataset, memory_cache=memory_cache, save_history=False, failed=history_failed
        )
        orphan_check = await Node.init(db=db, schema="CoreArtifactCheck")
        await orphan_check.new(
            db=db,
            name="Previous check without an artifact",
            origin=dataset.repository.repository_id,
            kind="ArtifactDefinition",
            validator=history.validator_id,
            conclusion=ValidatorConclusion.FAILURE.value if history_failed else ValidatorConclusion.SUCCESS.value,
            severity="critical" if history_failed else "info",
            message="Artifact could not be created",
            created_at=COMPLETED_AT,
            artifact_id=None,
        )
        await orphan_check.save(db=db)
        previous_checks = await NodeManager.query(
            db=db, schema="CoreArtifactCheck", filters={"validator__ids": [history.validator_id]}
        )
        assert len(previous_checks) == 7
        assert {check.id for check in previous_checks} == {
            outcome.check_id for outcome in history.outcomes.values()
        } | {orphan_check.id}
        original_execute = workflow_recorder.execute_workflow

        async def execute_check(**kwargs: Any) -> ArtifactCheckResult:
            outcome = await original_execute(**kwargs)
            request: CheckArtifactCreate = kwargs["parameters"]["model"]
            return ArtifactCheckResult(
                conclusion=outcome.conclusion, check_id=history.outcomes[request.target_id].check_id
            )

        monkeypatch.setattr(workflow_recorder, "execute_workflow", execute_check)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False)
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)
        monkeypatch.setitem(
            workflow_recorder.execute_results,
            GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
            ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE),
        )
        context = self._make_context(admin_account, default_branch)

        await validate_artifacts_generation(model=model, context=context)

        calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(calls) == 6
        assert {call["parameters"]["model"].target_id for call in calls} == {device.id for device in dataset.devices}
        record = await ArtifactRetryRecords(memory_cache).get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.completed is True
        assert record.failed_target_ids == {device.id for device in dataset.devices}
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
        retained_checks = await NodeManager.query(
            db=db, schema="CoreArtifactCheck", filters={"validator__ids": [history.validator_id]}
        )
        assert len(retained_checks) == 6
        assert {check.id for check in retained_checks} == {outcome.check_id for outcome in history.outcomes.values()}

        workflow_recorder.reset()
        monkeypatch.setitem(
            workflow_recorder.execute_results,
            GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name,
            ArtifactCheckResult(conclusion=ValidatorConclusion.SUCCESS),
        )
        await validate_artifacts_generation(model=model.model_copy(update={"retry_failed_only": True}), context=context)
        calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(calls) == 6
        assert {call["parameters"]["model"].target_id for call in calls} == {device.id for device in dataset.devices}
        record = await ArtifactRetryRecords(memory_cache).get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.failed_target_ids == frozenset()

    async def test_failed_target_outside_current_definition_rejects_without_dispatch(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        await ArtifactRetryRecords(memory_cache).complete(
            proposed_change_id=history.proposed_change_id,
            definition_id=dataset.definition.definition_id,
            record=ArtifactRetryRecord(validator_id=history.validator_id),
            completed_at=COMPLETED_AT,
            outcomes=history.outcomes | {str(uuid4()): ArtifactCheckResult(conclusion=ValidatorConclusion.FAILURE)},
        )
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        with pytest.raises(
            ValidationError, match=re.escape("a failed target no longer belongs to the artifact definition")
        ):
            await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))
        assert workflow_recorder.execute_calls == []
        await self._assert_history_unchanged(db=db, history=history)

    async def test_removed_failed_target_requires_ordinary_recovery_and_prunes_old_check(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        group = await NodeManager.get_one(
            db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
        )
        assert {relationship.peer_id for relationship in await group.members.get_relationships(db=db)} == {
            device.id for device in dataset.devices
        }
        remaining_ids = {device.id for device in dataset.devices[1:]}
        await group.members.update(db=db, data=list(remaining_ids))
        await group.members.save(db=db)
        try:
            model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
            context = self._make_context(admin_account, default_branch)
            await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)

            with pytest.raises(
                ValidationError, match=re.escape("a failed target no longer belongs to the artifact definition")
            ):
                await validate_artifacts_generation(model=model, context=context)
            assert workflow_recorder.execute_calls == []
            await self._assert_history_unchanged(db=db, history=history)

            original_execute = workflow_recorder.execute_workflow

            async def execute_check(**kwargs: Any) -> ArtifactCheckResult:
                await original_execute(**kwargs)
                request: CheckArtifactCreate = kwargs["parameters"]["model"]
                return ArtifactCheckResult(
                    conclusion=ValidatorConclusion.SUCCESS, check_id=history.outcomes[request.target_id].check_id
                )

            monkeypatch.setattr(workflow_recorder, "execute_workflow", execute_check)
            await validate_artifacts_generation(
                model=model.model_copy(update={"retry_failed_only": False}), context=context
            )
            calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert len(calls) == 5
            assert {call["parameters"]["model"].target_id for call in calls} == remaining_ids
            checks = await NodeManager.query(
                db=db, schema="CoreArtifactCheck", filters={"validator__ids": [history.validator_id]}
            )
            assert len(checks) == 5
            assert {check.id for check in checks} == {
                history.outcomes[target_id].check_id for target_id in remaining_ids
            }
            record = await ArtifactRetryRecords(memory_cache).get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            assert record is not None
            assert set(record.outcomes) == remaining_ids
            assert record.failed_target_ids == frozenset()

            default_group = await NodeManager.get_one(
                db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=default_branch, raise_on_error=True
            )
            assert {relationship.peer_id for relationship in await default_group.members.get_relationships(db=db)} == {
                device.id for device in dataset.devices
            }
        finally:
            restored_group = await NodeManager.get_one(
                db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
            )
            await restored_group.members.update(db=db, data=[device.id for device in dataset.devices])
            await restored_group.members.save(db=db)
            reloaded_group = await NodeManager.get_one(
                db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
            )
            assert {relationship.peer_id for relationship in await reloaded_group.members.get_relationships(db=db)} == {
                device.id for device in dataset.devices
            }

    async def test_successful_validator_is_noop_without_retry_history(
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
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)

        await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))

        assert workflow_recorder.execute_calls == []
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        assert validator.completed_at.value == COMPLETED_AT
        assert (
            await ArtifactRetryRecords(memory_cache).get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            is None
        )

    async def test_refresh_dispatches_failed_retry_without_diff_changes(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        definition_request = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        await set_diff_summary_cache(
            pipeline_id=definition_request.branch_diff.pipeline_id, diff_summary=[], cache=memory_cache
        )

        await refresh_artifacts(
            model=RequestProposedChangeRefreshArtifacts(
                proposed_change=history.proposed_change_id,
                source_branch=SOURCE_BRANCH,
                source_branch_sync_with_git=True,
                destination_branch=default_branch.name,
                branch_diff=definition_request.branch_diff,
                retry_failed_only=True,
            ),
            context=self._make_context(admin_account, default_branch),
        )

        calls = workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        assert len(calls) == 1
        request = calls[0]["parameters"]["model"]
        assert request.artifact_definition.definition_id == dataset.definition.definition_id
        assert request.retry_failed_only is True

    async def test_refresh_does_not_hide_incomplete_validator_history(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache, save_history=False)
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        validator.state.value = ValidatorState.IN_PROGRESS.value
        validator.conclusion.value = ValidatorConclusion.UNKNOWN.value
        validator.completed_at.value = None
        await validator.save(db=db)
        definition_request = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        context = self._make_context(admin_account, default_branch)

        await refresh_artifacts(
            model=RequestProposedChangeRefreshArtifacts(
                proposed_change=history.proposed_change_id,
                source_branch=SOURCE_BRANCH,
                source_branch_sync_with_git=True,
                destination_branch=default_branch.name,
                branch_diff=definition_request.branch_diff,
                retry_failed_only=True,
            ),
            context=context,
        )

        calls = workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        assert len(calls) == 1
        request = calls[0]["parameters"]["model"]
        assert request.artifact_definition.definition_id == dataset.definition.definition_id
        assert request.retry_failed_only is True
        with pytest.raises(ValidationError, match=re.escape("completed target history is missing or stale")):
            await validate_artifacts_generation(model=request, context=context)
        assert workflow_recorder.execute_calls == []
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.IN_PROGRESS.value
        assert validator.conclusion.value.value == ValidatorConclusion.UNKNOWN.value
        assert validator.completed_at.value is None

    async def test_refresh_recovers_missing_history_without_diff_changes(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache, save_history=False)
        definition_request = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        await set_diff_summary_cache(
            pipeline_id=definition_request.branch_diff.pipeline_id, diff_summary=[], cache=memory_cache
        )
        context = self._make_context(admin_account, default_branch)

        await refresh_artifacts(
            model=RequestProposedChangeRefreshArtifacts(
                proposed_change=history.proposed_change_id,
                source_branch=SOURCE_BRANCH,
                source_branch_sync_with_git=True,
                destination_branch=default_branch.name,
                branch_diff=definition_request.branch_diff,
            ),
            context=context,
        )

        calls = workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        assert len(calls) == 1
        request = calls[0]["parameters"]["model"]
        assert request.artifact_definition.definition_id == dataset.definition.definition_id
        assert request.retry_failed_only is False
        await validate_artifacts_generation(model=request, context=context)
        artifact_calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(artifact_calls) == 6
        assert {call["parameters"]["model"].target_id for call in artifact_calls} == {
            device.id for device in dataset.devices
        }

    async def test_failed_only_pipeline_reads_current_commits_without_git_or_diff(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        source_repository = await NodeManager.get_one(
            db=db,
            id=dataset.repository.repository_id,
            kind=InfrahubKind.REPOSITORY,
            branch=SOURCE_BRANCH,
            raise_on_error=True,
        )
        destination_repository = await NodeManager.get_one(
            db=db,
            id=dataset.repository.repository_id,
            kind=InfrahubKind.REPOSITORY,
            branch=default_branch,
            raise_on_error=True,
        )
        previous_source_commit = source_repository.commit.value
        previous_destination_commit = destination_repository.commit.value
        previous_status = source_repository.internal_status.value
        source_repository.commit.value = "current-source-commit"
        source_repository.internal_status.value = RepositoryInternalStatus.ACTIVE.value
        await source_repository.save(db=db)
        destination_repository.commit.value = "current-destination-commit"
        await destination_repository.save(db=db)
        model = RequestProposedChangePipeline(
            proposed_change=history.proposed_change_id,
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=True,
            destination_branch=default_branch.name,
            check_type=CheckType.ARTIFACT,
            retry_failed_only=True,
        )
        try:
            await run_proposed_change_pipeline(model=model, context=self._make_context(admin_account, default_branch))

            assert workflow_recorder.execute_calls == []
            assert [call["workflow"] for call in workflow_recorder.submit_calls] == [
                REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS
            ]
            request = workflow_recorder.submit_calls[0]["parameters"]["model"]
            assert request == RequestProposedChangeRefreshArtifacts(
                proposed_change=history.proposed_change_id,
                source_branch=SOURCE_BRANCH,
                source_branch_sync_with_git=True,
                destination_branch=default_branch.name,
                retry_failed_only=True,
                branch_diff=ProposedChangeBranchDiff(
                    pipeline_id=model.pipeline_id,
                    repositories=[
                        ProposedChangeRepository(
                            repository_id=dataset.repository.repository_id,
                            repository_name="retry-artifacts",
                            read_only=False,
                            source_branch=SOURCE_BRANCH,
                            destination_branch=default_branch.name,
                            internal_status=RepositoryInternalStatus.ACTIVE.value,
                            source_commit="current-source-commit",
                            destination_commit="current-destination-commit",
                        )
                    ],
                ),
            )
            with pytest.raises(
                ResourceNotFoundError,
                match=re.escape(f"Diff summary for pipeline {model.pipeline_id} was not found in the cache"),
            ):
                await get_diff_summary_cache(pipeline_id=model.pipeline_id)
            await self._assert_history_unchanged(db=db, history=history)
        finally:
            source_repository.commit.value = previous_source_commit
            source_repository.internal_status.value = previous_status
            await source_repository.save(db=db)
            destination_repository.commit.value = previous_destination_commit
            await destination_repository.save(db=db)

    async def test_uncertain_child_completion_leaves_retry_history_incomplete(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        original_execute = workflow_recorder.execute_workflow

        async def execute_check(**kwargs: Any) -> ArtifactCheckResult:
            await original_execute(**kwargs)
            request: CheckArtifactCreate = kwargs["parameters"]["model"]
            if request.target_id == dataset.devices[0].id:
                raise WorkflowOrchestrationError("Lost contact with the artifact worker before its final state")
            return ArtifactCheckResult(
                conclusion=ValidatorConclusion.SUCCESS, check_id=history.outcomes[request.target_id].check_id
            )

        monkeypatch.setattr(workflow_recorder, "execute_workflow", execute_check)
        context = self._make_context(admin_account, default_branch)

        with pytest.raises(
            WorkflowOrchestrationError,
            match=r"^Some artifact checks could not be followed to completion\. Retry history remains incomplete\.$",
        ):
            await validate_artifacts_generation(model=model, context=context)

        calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert len(calls) == 3
        assert {call["parameters"]["model"].target_id for call in calls} == {
            device.id for device in dataset.devices[:3]
        }
        records = ArtifactRetryRecords(memory_cache)
        record = await records.get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert record is not None
        assert record.completed is False
        assert record.completed_at is None
        assert record.outcomes == history.outcomes
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
        completed_at = validator.completed_at.value

        workflow_recorder.reset()
        with pytest.raises(ValidationError, match=re.escape("completed target history is missing or stale")):
            await validate_artifacts_generation(model=model, context=context)
        assert workflow_recorder.execute_calls == []
        assert (
            await records.get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            == record
        )
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
        assert validator.completed_at.value == completed_at
