from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from infrahub.artifacts.checks import artifact_check_name, save_artifact_check
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.core.constants import (
    CheckType,
    InfrahubKind,
    RepositoryInternalStatus,
    Severity,
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
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.workflow_override import override_workflow

from .conftest import ArtifactRegenTestBase, make_node_diff

if TYPE_CHECKING:
    from collections.abc import Collection

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

SOURCE_BRANCH = "feature/failed-artifact-retry"
COMPLETED_AT = "2025-01-01T12:00:00Z"
DEFINITION_NAME = "retry-device-config"
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
    artifact_ids: tuple[str | None, ...]
    """Artifact of each device on the source branch, in the order of `devices`."""

    group_id: str
    repository: ProposedChangeRepository
    definition: ProposedChangeArtifactDefinition


@dataclass(frozen=True)
class RetryHistory:
    proposed_change_id: str
    validator_id: str
    validator_conclusion: str
    check_ids: dict[str, str]
    """Check of each device, by device ID."""

    conclusions: dict[str, str]
    """Conclusion of each check, by check ID."""


class ArtifactCheckWorkflow(WorkflowRecorder):
    """Write each artifact check the way the artifact worker does, failing or losing the given targets."""

    def __init__(
        self, client: InfrahubClient, failing_target_ids: Collection[str] = (), lost_target_ids: Collection[str] = ()
    ) -> None:
        super().__init__()
        self.client = client
        self.failing_target_ids = set(failing_target_ids)
        self.lost_target_ids = set(lost_target_ids)

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
        if model.target_id in self.lost_target_ids:
            raise WorkflowOrchestrationError("Lost contact with the artifact worker before its final state")
        failed = model.target_id in self.failing_target_ids
        conclusion = ValidatorConclusion.FAILURE if failed else ValidatorConclusion.SUCCESS
        await save_artifact_check(
            client=self.client,
            validator_id=model.validator_id,
            check_id=model.check_id,
            artifact_id=model.artifact_id,
            name=artifact_check_name(artifact_name=model.artifact_name, target_name=model.target_name),
            origin=model.repository_id,
            conclusion=conclusion,
            severity=Severity.CRITICAL if failed else Severity.INFO,
            message="Failed to render artifact" if failed else "Artifact rendered successfully",
        )
        return conclusion


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
            name=DEFINITION_NAME,
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)
        source_branch = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)
        artifact_ids = []
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
            artifact_ids.append(artifact.id)
            query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP, branch=source_branch)
            await query_group.new(
                db=db, name=f"retry-query-{device.id}", query=query.id, members=[device], subscribers=[artifact]
            )
            await query_group.save(db=db)

        return RetryDataset(
            devices=tuple(devices),
            artifact_ids=tuple(artifact_ids),
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
                definition_name=DEFINITION_NAME,
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
        failed: bool = True,
        failures_without_artifacts: bool = False,
    ) -> RetryHistory:
        """Record a completed validator with one check per device, failed for the first three devices when `failed`.

        `failures_without_artifacts` writes the failed checks without their artifact, as earlier versions did.
        """
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db,
            name=f"retry-{uuid4()}",
            source_branch=SOURCE_BRANCH,
            destination_branch=dataset.repository.destination_branch,
        )
        await proposed_change.save(db=db)
        validator_conclusion = ValidatorConclusion.FAILURE.value if failed else ValidatorConclusion.SUCCESS.value
        validator = await Node.init(db=db, schema="CoreArtifactValidator")
        await validator.new(
            db=db,
            label=f"Artifact Validator: {DEFINITION_NAME}",
            definition=dataset.definition.definition_id,
            proposed_change=proposed_change,
            state=ValidatorState.COMPLETED.value,
            conclusion=validator_conclusion,
            started_at=COMPLETED_AT,
            completed_at=COMPLETED_AT,
        )
        await validator.save(db=db)
        check_ids = {}
        conclusions = {}
        for index, (device, artifact_id) in enumerate(zip(dataset.devices, dataset.artifact_ids, strict=True)):
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
                artifact_id=None
                if failures_without_artifacts and conclusion == ValidatorConclusion.FAILURE
                else artifact_id,
            )
            await check.save(db=db)
            check_ids[device.id] = check.id
            conclusions[check.id] = conclusion.value
        return RetryHistory(
            proposed_change_id=proposed_change.id,
            validator_id=validator.id,
            validator_conclusion=validator_conclusion,
            check_ids=check_ids,
            conclusions=conclusions,
        )

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

    async def _check_conclusions(self, *, db: InfrahubDatabase, validator_id: str) -> dict[str, str]:
        checks = await NodeManager.query(db=db, schema="CoreArtifactCheck", filters={"validator__ids": [validator_id]})
        return {check.id: check.conclusion.value.value for check in checks}

    async def _assert_validator(
        self, *, db: InfrahubDatabase, validator_id: str, state: ValidatorState, conclusion: ValidatorConclusion
    ) -> None:
        validator = await NodeManager.get_one(db=db, id=validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == state.value
        assert validator.conclusion.value.value == conclusion.value

    async def _assert_history_unchanged(self, *, db: InfrahubDatabase, history: RetryHistory) -> None:
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value.value == history.validator_conclusion
        assert validator.completed_at.value == COMPLETED_AT
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions


@dataclass
class RejectedRetryCase:
    name: str
    failed_checks: bool
    validator_state: ValidatorState
    validator_conclusion: ValidatorConclusion
    message: str


REJECTED_RETRY_CASES: list[RejectedRetryCase] = [
    RejectedRetryCase(
        name="validator_that_did_not_complete",
        failed_checks=True,
        validator_state=ValidatorState.IN_PROGRESS,
        validator_conclusion=ValidatorConclusion.UNKNOWN,
        message=f"The previous artifact checks of {DEFINITION_NAME} did not complete. Run the artifact checks again.",
    ),
    RejectedRetryCase(
        name="failed_validator_without_failed_checks",
        failed_checks=False,
        validator_state=ValidatorState.COMPLETED,
        validator_conclusion=ValidatorConclusion.FAILURE,
        message=f"No failed artifact check was found for {DEFINITION_NAME}. Run the artifact checks again.",
    ),
]


@dataclass
class FailedRefreshCase:
    name: str
    validator_state: ValidatorState
    validator_conclusion: ValidatorConclusion


FAILED_REFRESH_CASES: list[FailedRefreshCase] = [
    FailedRefreshCase(
        name="failed_validator",
        validator_state=ValidatorState.COMPLETED,
        validator_conclusion=ValidatorConclusion.FAILURE,
    ),
    FailedRefreshCase(
        name="validator_that_did_not_complete",
        validator_state=ValidatorState.IN_PROGRESS,
        validator_conclusion=ValidatorConclusion.UNKNOWN,
    ),
]


class TestFailedArtifactRetry(ArtifactRetryTestBase):
    async def test_failed_retry_renders_only_failed_targets_and_reuses_their_checks(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        context = self._make_context(admin_account, default_branch)
        workflow = ArtifactCheckWorkflow(client=client)

        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            await validate_artifacts_generation(model=model, context=context)
            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert {call["parameters"]["model"].target_id: call["parameters"]["model"].check_id for call in calls} == {
                device.id: history.check_ids[device.id] for device in dataset.devices[:3]
            }
            assert len(calls) == 3
            assert await self._check_conclusions(db=db, validator_id=history.validator_id) == dict.fromkeys(
                history.check_ids.values(), ValidatorConclusion.SUCCESS.value
            )
            await self._assert_validator(
                db=db,
                validator_id=history.validator_id,
                state=ValidatorState.COMPLETED,
                conclusion=ValidatorConclusion.SUCCESS,
            )

            workflow.reset()
            await validate_artifacts_generation(model=model, context=context)
            assert workflow.execute_calls == []

    async def test_change_run_keeps_failures_of_targets_it_does_not_render(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False)
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)

        await validate_artifacts_generation(model=model, context=self._make_context(admin_account, default_branch))

        calls = workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert sorted(call["parameters"]["model"].target_id for call in calls) == sorted(
            device.id for device in dataset.devices[3:5]
        )
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.FAILURE,
        )
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions

    async def test_failures_written_without_artifacts_are_retried_without_rendering_every_target(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, failures_without_artifacts=True)
        orphan_check = await Node.init(db=db, schema="CoreArtifactCheck")
        await orphan_check.new(
            db=db,
            name="device-config: removed-device",
            origin=dataset.repository.repository_id,
            kind="ArtifactDefinition",
            validator=history.validator_id,
            conclusion=ValidatorConclusion.FAILURE.value,
            severity="critical",
            message="Previous render result",
            created_at=COMPLETED_AT,
        )
        await orphan_check.save(db=db)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False)
        await self._set_changed_successes(dataset=dataset, model=model, memory_cache=memory_cache)
        context = self._make_context(admin_account, default_branch)
        workflow = ArtifactCheckWorkflow(client=client)

        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            await validate_artifacts_generation(model=model, context=context)
            changed_calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            assert sorted(call["parameters"]["model"].target_id for call in changed_calls) == sorted(
                device.id for device in dataset.devices[3:5]
            )
            assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions
            await self._assert_validator(
                db=db,
                validator_id=history.validator_id,
                state=ValidatorState.COMPLETED,
                conclusion=ValidatorConclusion.FAILURE,
            )

            workflow.reset()
            await validate_artifacts_generation(
                model=model.model_copy(update={"retry_failed_only": True}), context=context
            )
            retry_calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)

        assert sorted(
            (call["parameters"]["model"].target_id, call["parameters"]["model"].check_id) for call in retry_calls
        ) == sorted((device.id, history.check_ids[device.id]) for device in dataset.devices[:3])
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == dict.fromkeys(
            history.check_ids.values(), ValidatorConclusion.SUCCESS.value
        )
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.SUCCESS,
        )

    async def test_failed_retry_deletes_the_failed_check_of_a_target_that_left_the_definition(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        group = await NodeManager.get_one(
            db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
        )
        remaining_devices = dataset.devices[1:]
        await group.members.update(db=db, data=[device.id for device in remaining_devices])
        await group.members.save(db=db)
        workflow = ArtifactCheckWorkflow(client=client)
        try:
            with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
                await validate_artifacts_generation(
                    model=self._request(dataset=dataset, proposed_change_id=history.proposed_change_id),
                    context=self._make_context(admin_account, default_branch),
                )
        finally:
            restored_group = await NodeManager.get_one(
                db=db, id=dataset.group_id, kind=InfrahubKind.STANDARDGROUP, branch=SOURCE_BRANCH, raise_on_error=True
            )
            await restored_group.members.update(db=db, data=[device.id for device in dataset.devices])
            await restored_group.members.save(db=db)

        calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        assert sorted(call["parameters"]["model"].target_id for call in calls) == sorted(
            device.id for device in dataset.devices[1:3]
        )
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == {
            history.check_ids[device.id]: ValidatorConclusion.SUCCESS.value for device in remaining_devices
        }
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.SUCCESS,
        )

    async def test_failed_retry_of_a_passed_validator_does_nothing(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, failed=False)

        await validate_artifacts_generation(
            model=self._request(dataset=dataset, proposed_change_id=history.proposed_change_id),
            context=self._make_context(admin_account, default_branch),
        )

        assert workflow_recorder.execute_calls == []
        await self._assert_history_unchanged(db=db, history=history)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REJECTED_RETRY_CASES])
    async def test_failed_retry_rejects_a_validator_without_retryable_checks(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        test_case: RejectedRetryCase,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, failed=test_case.failed_checks)
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        validator.state.value = test_case.validator_state.value
        validator.conclusion.value = test_case.validator_conclusion.value
        await validator.save(db=db)

        with pytest.raises(ValidationError, match=rf"^{re.escape(test_case.message)}$"):
            await validate_artifacts_generation(
                model=self._request(dataset=dataset, proposed_change_id=history.proposed_change_id),
                context=self._make_context(admin_account, default_branch),
            )

        assert workflow_recorder.execute_calls == []
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=test_case.validator_state,
            conclusion=test_case.validator_conclusion,
        )
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FAILED_REFRESH_CASES])
    async def test_failed_refresh_dispatches_a_definition_that_did_not_pass_without_diff_changes(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        test_case: FailedRefreshCase,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        validator.state.value = test_case.validator_state.value
        validator.conclusion.value = test_case.validator_conclusion.value
        await validator.save(db=db)
        definition_request = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)

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
        assert [
            (
                call["parameters"]["model"].artifact_definition.definition_id,
                call["parameters"]["model"].retry_failed_only,
            )
            for call in calls
        ] == [(dataset.definition.definition_id, True)]

    async def test_change_refresh_skips_a_failed_definition_without_changes(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
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
            ),
            context=self._make_context(admin_account, default_branch),
        )

        assert workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK) == []

    async def test_failed_only_pipeline_reads_current_commits_without_git_or_diff(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
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

    async def test_a_lost_target_keeps_its_check_for_the_next_retry(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        client: InfrahubClient,
        dependency_provider: Provider,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        context = self._make_context(admin_account, default_branch)
        lost_device = dataset.devices[0]
        workflow = ArtifactCheckWorkflow(client=client, lost_target_ids=[lost_device.id])

        with override_workflow(workflow=workflow, dependency_provider=dependency_provider):
            await validate_artifacts_generation(model=model, context=context)
            assert len(workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)) == 3
            assert await self._check_conclusions(db=db, validator_id=history.validator_id) == {
                check_id: ValidatorConclusion.FAILURE.value
                if check_id == history.check_ids[lost_device.id]
                else ValidatorConclusion.SUCCESS.value
                for check_id in history.check_ids.values()
            }
            await self._assert_validator(
                db=db,
                validator_id=history.validator_id,
                state=ValidatorState.COMPLETED,
                conclusion=ValidatorConclusion.FAILURE,
            )

            workflow.reset()
            workflow.lost_target_ids.clear()
            await validate_artifacts_generation(model=model, context=context)
            calls = workflow.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)

        assert [(call["parameters"]["model"].target_id, call["parameters"]["model"].check_id) for call in calls] == [
            (lost_device.id, history.check_ids[lost_device.id])
        ]
        await self._assert_validator(
            db=db,
            validator_id=history.validator_id,
            state=ValidatorState.COMPLETED,
            conclusion=ValidatorConclusion.SUCCESS,
        )
