from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import State, StateType

from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.artifacts.tasks import create as check_artifact_target
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import (
    CheckType,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
    ValidatorConclusion,
    ValidatorState,
)
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.message_bus.types import ProposedChangeArtifactDefinition, ProposedChangeBranchDiff
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.proposed_change.models import RequestArtifactDefinitionCheck, RequestProposedChangePipeline
from infrahub.proposed_change.tasks import validate_artifacts_generation
from infrahub.services import InfrahubServices
from infrahub.tasks.dummy import dummy_flow
from infrahub.webhook.tasks.process import webhook_send
from infrahub.workflows.catalogue import REQUEST_PROPOSED_CHANGE_PIPELINE, WEBHOOK_SEND
from infrahub.workflows.constants import TAG_NAMESPACE
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.graphql import graphql_mutation
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from graphql import ExecutionResult
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

RETRY_TASK = """
mutation RetryTask($id: String!) {
    InfrahubTaskRetry(data: {id: $id}) {
        ok
        task {
            id
        }
    }
}
"""

CANCEL_TASK = """
mutation CancelTask($id: String!) {
    InfrahubTaskCancel(data: {id: $id}) {
        ok
    }
}
"""

ARTIFACT_NAME = "configuration"
FAILED_ARTIFACT_ID = "17b3b2f0-89aa-4fdd-8beb-c1e5b0e5d661"
PASSED_ARTIFACT_ID = "17b3b2f0-89aa-4fdd-8beb-c1e5b0e5d662"
WEBHOOK_ID = "17b3b2f0-89aa-4fdd-8beb-c1e5b0e5d663"
WEBHOOK_PARAMETERS: dict[str, Any] = {
    "webhook_id": WEBHOOK_ID,
    "webhook_kind": InfrahubKind.STANDARDWEBHOOK,
    "webhook_name": "component-test-webhook",
    "payload": {"event_type": "branch.created"},
    "branch_name": "main",
}


@dataclass(frozen=True)
class ArtifactChecks:
    """The artifact checks of two proposed changes, as an earlier run of the checks left them."""

    source_branch: Branch
    repository_id: str
    proposed_change_id: str

    definition_id: str
    validator_id: str
    """The validator of `definition_id`, which completed with a failure."""

    failed_check_id: str
    """Reports on the artifact `FAILED_ARTIFACT_ID` and is named `configuration: device-failed`."""

    unfinished_check_id: str
    """Reports on no artifact and is named `configuration: device-unfinished`."""

    passed_check_id: str
    """Reports on the artifact `PASSED_ARTIFACT_ID` and is named `configuration: device-passed`."""

    passed_definition_id: str
    passed_validator_id: str
    """The validator of `passed_definition_id`, which completed with a success."""

    leftover_failed_check_id: str
    """A failed check that the validator of `passed_definition_id` still has."""

    resolved_definition_id: str
    """Its validator completed with a failure and its only check passed."""

    running_definition_id: str
    running_validator_id: str
    """The validator of `running_definition_id`, which is in progress."""

    running_failed_check_id: str

    closed_proposed_change_id: str
    closed_validator_id: str
    closed_failed_check_id: str


class ArtifactTask(StrEnum):
    TARGET = "target"
    DEFINITION = "definition"


def target_parameters(
    checks: ArtifactChecks,
    validator_id: str,
    target_name: str,
    check_id: str | None = None,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    """Return the parameters a run that checks one artifact target is stored with."""
    account = AccountSession(authenticated=True, account_id=str(uuid4()), auth_type=AuthType.API)
    model = CheckArtifactCreate(
        artifact_name=ARTIFACT_NAME,
        artifact_definition=checks.definition_id,
        artifact_definition_name="retry-definition",
        commit="0123456789abcdef0123456789abcdef01234567",
        content_type="text/plain",
        transform_type=InfrahubKind.TRANSFORMJINJA2,
        transform_location="template.j2",
        repository_id=checks.repository_id,
        repository_name="task-retry-repository",
        repository_kind=InfrahubKind.REPOSITORY,
        branch_name=checks.source_branch.name,
        target_id=str(uuid4()),
        target_kind="TestDevice",
        target_name=target_name,
        artifact_id=artifact_id,
        query="TaskRetryQuery",
        query_id=str(uuid4()),
        timeout=10,
        variables={},
        validator_id=validator_id,
        check_id=check_id,
        context=InfrahubContext.init(branch=checks.source_branch, account=account),
    )
    return {"model": model.model_dump(mode="json")}


def definition_parameters(checks: ArtifactChecks, proposed_change_id: str, definition_id: str) -> dict[str, Any]:
    """Return the parameters a run that checks the targets of one artifact definition is stored with."""
    account = AccountSession(authenticated=True, account_id=str(uuid4()), auth_type=AuthType.API)
    model = RequestArtifactDefinitionCheck(
        artifact_definition=ProposedChangeArtifactDefinition(
            definition_id=definition_id,
            definition_name="retry-definition",
            artifact_name=ARTIFACT_NAME,
            query_name="TaskRetryQuery",
            query_id=str(uuid4()),
            query_payload="query { CoreRepository { edges { node { id } } } }",
            repository_id=checks.repository_id,
            transform_kind=InfrahubKind.TRANSFORMJINJA2,
            content_type="text/plain",
            timeout=10,
        ),
        branch_diff=ProposedChangeBranchDiff(pipeline_id=uuid4()),
        proposed_change=proposed_change_id,
        source_branch=checks.source_branch.name,
        source_branch_sync_with_git=False,
        destination_branch="main",
    )
    context = InfrahubContext.init(branch=checks.source_branch, account=account)
    return {"model": model.model_dump(mode="json"), "context": context.model_dump(mode="json")}


@dataclass
class TargetRetryCase:
    name: str
    build_parameters: Callable[[ArtifactChecks], dict[str, Any]]
    retried_check: Callable[[ArtifactChecks], str]


TARGET_RETRY_CASES: list[TargetRetryCase] = [
    TargetRetryCase(
        name="check_named_by_the_run",
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=checks.validator_id, check_id=checks.failed_check_id, target_name="renamed"
        ),
        retried_check=lambda checks: checks.failed_check_id,
    ),
    TargetRetryCase(
        name="check_of_the_same_artifact",
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=checks.validator_id, artifact_id=FAILED_ARTIFACT_ID, target_name="renamed"
        ),
        retried_check=lambda checks: checks.failed_check_id,
    ),
    TargetRetryCase(
        name="check_of_the_same_name_when_the_run_names_no_artifact",
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=checks.validator_id, target_name="device-unfinished"
        ),
        retried_check=lambda checks: checks.unfinished_check_id,
    ),
    TargetRetryCase(
        name="check_of_the_same_name_when_no_check_reports_on_the_artifact",
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=checks.validator_id, artifact_id=str(uuid4()), target_name="device-unfinished"
        ),
        retried_check=lambda checks: checks.unfinished_check_id,
    ),
]


@dataclass
class RefusalCase:
    name: str
    task: ArtifactTask
    build_parameters: Callable[[ArtifactChecks], dict[str, Any]]
    expected_error: str
    state: StateType = StateType.COMPLETED


REFUSAL_CASES: list[RefusalCase] = [
    RefusalCase(
        name="target_task_still_running",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=checks.validator_id, check_id=checks.failed_check_id, target_name="device"
        ),
        expected_error="Retry is unavailable: Artifact check still in progress.",
        state=StateType.RUNNING,
    ),
    RefusalCase(
        name="target_check_passed",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks,
            validator_id=checks.validator_id,
            check_id=checks.passed_check_id,
            target_name="device-passed",
        ),
        expected_error="The artifact check 'configuration: device-passed' passed, so there is nothing to retry.",
    ),
    RefusalCase(
        name="target_check_of_the_same_artifact_passed",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=checks.validator_id, artifact_id=PASSED_ARTIFACT_ID, target_name="device-passed"
        ),
        expected_error="The artifact check 'configuration: device-passed' passed, so there is nothing to retry.",
    ),
    RefusalCase(
        name="target_validator_no_longer_exists",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=str(uuid4()), check_id=checks.failed_check_id, target_name="device-failed"
        ),
        expected_error=(
            "The artifact validator of this task was not found. Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="target_check_named_by_the_run_no_longer_exists",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks,
            validator_id=checks.validator_id,
            check_id=str(uuid4()),
            artifact_id=FAILED_ARTIFACT_ID,
            target_name="device-failed",
        ),
        expected_error=(
            "The artifact check of this task was not found. Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="target_check_named_by_the_run_belongs_to_another_validator",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks,
            validator_id=checks.validator_id,
            check_id=checks.closed_failed_check_id,
            target_name="device-failed",
        ),
        expected_error=(
            "The artifact check of this task was not found. Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="target_no_check_of_the_same_artifact_or_name",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks, validator_id=checks.validator_id, artifact_id=str(uuid4()), target_name="device-removed"
        ),
        expected_error=(
            "The artifact check of this task was not found. Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="target_checks_of_the_validator_not_complete",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks,
            validator_id=checks.running_validator_id,
            check_id=checks.running_failed_check_id,
            target_name="device-failed",
        ),
        expected_error=(
            "The artifact checks of this task's validator are not complete (state: in_progress). "
            "If they are still running, retry after they finish. "
            "Otherwise, run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="target_check_failed_but_the_validator_passed",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks,
            validator_id=checks.passed_validator_id,
            check_id=checks.leftover_failed_check_id,
            target_name="device-leftover",
        ),
        expected_error="The artifact checks of this task's validator passed, so there is nothing to retry.",
    ),
    RefusalCase(
        name="target_proposed_change_closed",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: target_parameters(
            checks=checks,
            validator_id=checks.closed_validator_id,
            check_id=checks.closed_failed_check_id,
            target_name="device-failed",
        ),
        expected_error="Unable to trigger check on proposed changes that aren't in the open state",
    ),
    RefusalCase(
        name="target_parameters_name_no_validator",
        task=ArtifactTask.TARGET,
        build_parameters=lambda checks: {"model": {"target_name": "device-failed"}},  # noqa: ARG005
        expected_error=(
            "The parameters stored for this task do not identify its artifact validator. "
            "Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="definition_task_still_running",
        task=ArtifactTask.DEFINITION,
        build_parameters=lambda checks: definition_parameters(
            checks=checks, proposed_change_id=checks.proposed_change_id, definition_id=checks.definition_id
        ),
        expected_error="Retry is unavailable: Artifact check still in progress.",
        state=StateType.RUNNING,
    ),
    RefusalCase(
        name="definition_validator_no_longer_exists",
        task=ArtifactTask.DEFINITION,
        build_parameters=lambda checks: definition_parameters(
            checks=checks, proposed_change_id=checks.proposed_change_id, definition_id=str(uuid4())
        ),
        expected_error=(
            "The artifact validator of this task was not found. Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="definition_proposed_change_no_longer_exists",
        task=ArtifactTask.DEFINITION,
        build_parameters=lambda checks: definition_parameters(
            checks=checks, proposed_change_id=str(uuid4()), definition_id=checks.definition_id
        ),
        expected_error=(
            "The artifact validator of this task was not found. Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="definition_checks_of_the_validator_not_complete",
        task=ArtifactTask.DEFINITION,
        build_parameters=lambda checks: definition_parameters(
            checks=checks, proposed_change_id=checks.proposed_change_id, definition_id=checks.running_definition_id
        ),
        expected_error=(
            "The artifact checks of this task's validator are not complete (state: in_progress). "
            "If they are still running, retry after they finish. "
            "Otherwise, run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="definition_checks_passed",
        task=ArtifactTask.DEFINITION,
        build_parameters=lambda checks: definition_parameters(
            checks=checks, proposed_change_id=checks.proposed_change_id, definition_id=checks.passed_definition_id
        ),
        expected_error="The artifact checks of this task's validator passed, so there is nothing to retry.",
    ),
    RefusalCase(
        name="definition_validator_has_no_failed_or_unfinished_check",
        task=ArtifactTask.DEFINITION,
        build_parameters=lambda checks: definition_parameters(
            checks=checks, proposed_change_id=checks.proposed_change_id, definition_id=checks.resolved_definition_id
        ),
        expected_error=(
            "No failed or unfinished artifact check was found for this task's validator. "
            "Run the artifact checks of the proposed change again."
        ),
    ),
    RefusalCase(
        name="definition_proposed_change_closed",
        task=ArtifactTask.DEFINITION,
        build_parameters=lambda checks: definition_parameters(
            checks=checks, proposed_change_id=checks.closed_proposed_change_id, definition_id=checks.definition_id
        ),
        expected_error="Unable to trigger check on proposed changes that aren't in the open state",
    ),
]


class TestTaskRetry:
    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_test_fixture: None) -> AsyncGenerator[PrefectClient, None]:
        async with get_client(sync_client=False) as client:
            yield client

    @pytest.fixture(scope="class")
    async def requester(
        self,
        db: InfrahubDatabase,
        register_core_models_schema_scope_class: SchemaBranch,
        default_permission_backend_scope_class: None,
    ) -> AccountSession:
        """An account that holds no permission."""
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name="task-retry-requester", password="task-retry-requester-password")
        await account.save(db=db)
        return AccountSession(authenticated=True, account_id=account.id, auth_type=AuthType.API)

    @pytest.fixture(scope="class")
    async def webhook_operator(
        self,
        db: InfrahubDatabase,
        register_core_models_schema_scope_class: SchemaBranch,
        default_permission_backend_scope_class: None,
    ) -> AccountSession:
        """An account allowed to update standard webhooks on the default branch."""
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name="webhook-operator", password="webhook-operator-password")
        await account.save(db=db)
        await define_permissions(
            account=account,
            db=db,
            object_permissions=[
                ObjectPermission(
                    namespace="Core",
                    name="StandardWebhook",
                    action=PermissionAction.UPDATE.value,
                    decision=PermissionDecision.ALLOW_DEFAULT.value,
                )
            ],
            role_name="webhook-operators",
            group_name="webhook-operators",
        )
        return AccountSession(authenticated=True, account_id=account.id, auth_type=AuthType.API)

    @pytest.fixture(scope="class")
    async def artifact_checks(
        self, db: InfrahubDatabase, register_core_models_schema_scope_class: SchemaBranch
    ) -> ArtifactChecks:
        source_branch = await create_branch(db=db, branch_name="task-retry-artifacts")
        repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repository.new(db=db, name="task-retry-repository", location="https://git.example.com/artifacts.git")
        await repository.save(db=db)
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="task-retry-targets")
        await group.save(db=db)
        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="TaskRetryQuery", query="query { CoreRepository { edges { node { id } } } }")
        await query.save(db=db)
        transformation = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await transformation.new(
            db=db, name="task-retry-transform", query=query, repository=repository, template_path="template.j2"
        )
        await transformation.save(db=db)

        async def create_proposed_change(name: str, state: ProposedChangeState) -> Node:
            proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
            await proposed_change.new(
                db=db, name=name, destination_branch="main", source_branch=source_branch.name, state=state.value
            )
            await proposed_change.save(db=db)
            return proposed_change

        async def create_definition(name: str) -> Node:
            definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
            await definition.new(
                db=db,
                name=name,
                artifact_name=ARTIFACT_NAME,
                content_type="text/plain",
                parameters={"value": {}},
                targets=group,
                transformation=transformation,
            )
            await definition.save(db=db)
            return definition

        async def create_validator(
            proposed_change: Node,
            definition: Node,
            conclusion: ValidatorConclusion,
            state: ValidatorState = ValidatorState.COMPLETED,
        ) -> Node:
            validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
            await validator.new(
                db=db,
                proposed_change=proposed_change,
                definition=definition,
                state=state.value,
                conclusion=conclusion.value,
            )
            await validator.save(db=db)
            return validator

        async def create_check(
            validator: Node, target_name: str, conclusion: ValidatorConclusion, artifact_id: str | None = None
        ) -> Node:
            check = await Node.init(db=db, schema=InfrahubKind.ARTIFACTCHECK)
            await check.new(
                db=db,
                name=f"{ARTIFACT_NAME}: {target_name}",
                origin=repository.id,
                kind="ArtifactDefinition",
                validator=validator,
                conclusion=conclusion.value,
                artifact_id=artifact_id,
            )
            await check.save(db=db)
            return check

        proposed_change = await create_proposed_change(name="task-retry-open", state=ProposedChangeState.OPEN)
        definition = await create_definition(name="retry-definition")
        validator = await create_validator(
            proposed_change=proposed_change, definition=definition, conclusion=ValidatorConclusion.FAILURE
        )
        failed_check = await create_check(
            validator=validator,
            target_name="device-failed",
            conclusion=ValidatorConclusion.FAILURE,
            artifact_id=FAILED_ARTIFACT_ID,
        )
        unfinished_check = await create_check(
            validator=validator, target_name="device-unfinished", conclusion=ValidatorConclusion.UNKNOWN
        )
        passed_check = await create_check(
            validator=validator,
            target_name="device-passed",
            conclusion=ValidatorConclusion.SUCCESS,
            artifact_id=PASSED_ARTIFACT_ID,
        )

        passed_definition = await create_definition(name="passed-definition")
        passed_validator = await create_validator(
            proposed_change=proposed_change, definition=passed_definition, conclusion=ValidatorConclusion.SUCCESS
        )
        await create_check(
            validator=passed_validator, target_name="device-passed", conclusion=ValidatorConclusion.SUCCESS
        )
        leftover_failed_check = await create_check(
            validator=passed_validator, target_name="device-leftover", conclusion=ValidatorConclusion.FAILURE
        )

        resolved_definition = await create_definition(name="resolved-definition")
        resolved_validator = await create_validator(
            proposed_change=proposed_change, definition=resolved_definition, conclusion=ValidatorConclusion.FAILURE
        )
        await create_check(
            validator=resolved_validator, target_name="device-passed", conclusion=ValidatorConclusion.SUCCESS
        )

        running_definition = await create_definition(name="running-definition")
        running_validator = await create_validator(
            proposed_change=proposed_change,
            definition=running_definition,
            conclusion=ValidatorConclusion.UNKNOWN,
            state=ValidatorState.IN_PROGRESS,
        )
        running_failed_check = await create_check(
            validator=running_validator, target_name="device-failed", conclusion=ValidatorConclusion.FAILURE
        )

        closed_proposed_change = await create_proposed_change(
            name="task-retry-closed", state=ProposedChangeState.CLOSED
        )
        closed_validator = await create_validator(
            proposed_change=closed_proposed_change, definition=definition, conclusion=ValidatorConclusion.FAILURE
        )
        closed_failed_check = await create_check(
            validator=closed_validator, target_name="device-failed", conclusion=ValidatorConclusion.FAILURE
        )

        return ArtifactChecks(
            source_branch=source_branch,
            repository_id=repository.id,
            proposed_change_id=proposed_change.id,
            definition_id=definition.id,
            validator_id=validator.id,
            failed_check_id=failed_check.id,
            unfinished_check_id=unfinished_check.id,
            passed_check_id=passed_check.id,
            passed_definition_id=passed_definition.id,
            passed_validator_id=passed_validator.id,
            leftover_failed_check_id=leftover_failed_check.id,
            resolved_definition_id=resolved_definition.id,
            running_definition_id=running_definition.id,
            running_validator_id=running_validator.id,
            running_failed_check_id=running_failed_check.id,
            closed_proposed_change_id=closed_proposed_change.id,
            closed_validator_id=closed_validator.id,
            closed_failed_check_id=closed_failed_check.id,
        )

    async def create_run(
        self,
        prefect_client: PrefectClient,
        flow: Flow[Any, Any],
        parameters: dict[str, Any],
        state: StateType = StateType.COMPLETED,
    ) -> FlowRun:
        return await prefect_client.create_flow_run(
            flow=flow, parameters=parameters, tags=[TAG_NAMESPACE], state=State(type=state)
        )

    async def create_artifact_run(
        self,
        prefect_client: PrefectClient,
        task: ArtifactTask,
        parameters: dict[str, Any],
        state: StateType = StateType.COMPLETED,
    ) -> FlowRun:
        flow = check_artifact_target if task == ArtifactTask.TARGET else validate_artifacts_generation
        return await self.create_run(prefect_client=prefect_client, flow=flow, parameters=parameters, state=state)

    async def run_mutation(
        self,
        db: InfrahubDatabase,
        recorder: WorkflowRecorder,
        account_session: AccountSession,
        task_id: str,
        mutation: str = RETRY_TASK,
    ) -> ExecutionResult:
        service = await InfrahubServices.new(database=db, workflow=recorder)
        return await graphql_mutation(
            query=mutation, db=db, variables={"id": task_id}, service=service, account_session=account_session
        )

    def assert_checks_requested(self, result: ExecutionResult) -> None:
        """The task history lists no run for the request, so the retry of an artifact check task returns none."""
        assert result.errors is None
        assert result.data == {"InfrahubTaskRetry": {"ok": True, "task": None}}

    def expected_pipeline_request(
        self,
        checks: ArtifactChecks,
        submitted: RequestProposedChangePipeline,
        check_ids: list[str] | None,
    ) -> RequestProposedChangePipeline:
        return RequestProposedChangePipeline(
            pipeline_id=submitted.pipeline_id,
            proposed_change=checks.proposed_change_id,
            source_branch="task-retry-artifacts",
            source_branch_sync_with_git=False,
            destination_branch="main",
            check_type=CheckType.ARTIFACT,
            retry_failed_only=True,
            validator_id=checks.validator_id,
            check_ids=check_ids,
        )

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in TARGET_RETRY_CASES])
    async def test_retry_of_a_target_task_requests_a_failed_only_run_of_its_check(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        requester: AccountSession,
        artifact_checks: ArtifactChecks,
        case: TargetRetryCase,
    ) -> None:
        run = await self.create_artifact_run(
            prefect_client=prefect_client, task=ArtifactTask.TARGET, parameters=case.build_parameters(artifact_checks)
        )
        recorder = WorkflowRecorder()

        result = await self.run_mutation(db=db, recorder=recorder, account_session=requester, task_id=str(run.id))

        self.assert_checks_requested(result=result)
        assert len(recorder.submit_calls) == 1
        submitted = recorder.submit_calls[0]["parameters"]["model"]
        assert recorder.submit_calls == [
            {
                "kind": "submit",
                "workflow": REQUEST_PROPOSED_CHANGE_PIPELINE,
                "parameters": {
                    "model": self.expected_pipeline_request(
                        checks=artifact_checks, submitted=submitted, check_ids=[case.retried_check(artifact_checks)]
                    )
                },
                "tags": [],
            }
        ]

    async def test_retry_of_a_definition_task_requests_a_failed_only_run_of_its_validator(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        requester: AccountSession,
        artifact_checks: ArtifactChecks,
    ) -> None:
        run = await self.create_artifact_run(
            prefect_client=prefect_client,
            task=ArtifactTask.DEFINITION,
            parameters=definition_parameters(
                checks=artifact_checks,
                proposed_change_id=artifact_checks.proposed_change_id,
                definition_id=artifact_checks.definition_id,
            ),
        )
        recorder = WorkflowRecorder()

        result = await self.run_mutation(db=db, recorder=recorder, account_session=requester, task_id=str(run.id))

        self.assert_checks_requested(result=result)
        assert len(recorder.submit_calls) == 1
        submitted = recorder.submit_calls[0]["parameters"]["model"]
        assert recorder.submit_calls == [
            {
                "kind": "submit",
                "workflow": REQUEST_PROPOSED_CHANGE_PIPELINE,
                "parameters": {
                    "model": self.expected_pipeline_request(checks=artifact_checks, submitted=submitted, check_ids=None)
                },
                "tags": [],
            }
        ]

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSAL_CASES])
    async def test_retry_of_an_artifact_task_is_refused_and_submits_nothing(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        requester: AccountSession,
        artifact_checks: ArtifactChecks,
        case: RefusalCase,
    ) -> None:
        run = await self.create_artifact_run(
            prefect_client=prefect_client,
            task=case.task,
            parameters=case.build_parameters(artifact_checks),
            state=case.state,
        )
        recorder = WorkflowRecorder()

        result = await self.run_mutation(db=db, recorder=recorder, account_session=requester, task_id=str(run.id))

        assert result.errors
        assert [error.message for error in result.errors] == [case.expected_error]
        assert recorder.calls == []

    @pytest.mark.parametrize("task", list(ArtifactTask))
    async def test_cancel_of_an_artifact_task_is_not_supported(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        requester: AccountSession,
        artifact_checks: ArtifactChecks,
        task: ArtifactTask,
    ) -> None:
        parameters = (
            target_parameters(
                checks=artifact_checks,
                validator_id=artifact_checks.validator_id,
                check_id=artifact_checks.failed_check_id,
                target_name="device-failed",
            )
            if task == ArtifactTask.TARGET
            else definition_parameters(
                checks=artifact_checks,
                proposed_change_id=artifact_checks.proposed_change_id,
                definition_id=artifact_checks.definition_id,
            )
        )
        run = await self.create_artifact_run(
            prefect_client=prefect_client, task=task, parameters=parameters, state=StateType.RUNNING
        )

        result = await self.run_mutation(
            db=db, recorder=WorkflowRecorder(), account_session=requester, task_id=str(run.id), mutation=CANCEL_TASK
        )

        assert result.errors
        assert [error.message for error in result.errors] == [
            "Cancel is unavailable: it is not supported for this task."
        ]
        unchanged = await prefect_client.read_flow_run(flow_run_id=run.id)
        assert unchanged.state_type == StateType.RUNNING

    async def test_retry_of_a_delivery_replays_the_parameters_stored_with_the_run(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, webhook_operator: AccountSession
    ) -> None:
        run = await self.create_run(prefect_client=prefect_client, flow=webhook_send, parameters=WEBHOOK_PARAMETERS)
        recorder = WorkflowRecorder()

        result = await self.run_mutation(
            db=db, recorder=recorder, account_session=webhook_operator, task_id=str(run.id)
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubTaskRetry"]["ok"] is True
        assert UUID(result.data["InfrahubTaskRetry"]["task"]["id"])
        assert recorder.calls == [
            {
                "kind": "submit",
                "workflow": WEBHOOK_SEND,
                "parameters": {
                    "webhook_id": WEBHOOK_ID,
                    "webhook_kind": "CoreStandardWebhook",
                    "webhook_name": "component-test-webhook",
                    "payload": {"event_type": "branch.created"},
                    "branch_name": "main",
                },
                "tags": [f"infrahub.app/node/{WEBHOOK_ID}"],
            }
        ]

    async def test_retry_of_a_delivery_in_progress_is_refused(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, webhook_operator: AccountSession
    ) -> None:
        run = await self.create_run(
            prefect_client=prefect_client, flow=webhook_send, parameters=WEBHOOK_PARAMETERS, state=StateType.SCHEDULED
        )
        recorder = WorkflowRecorder()

        result = await self.run_mutation(
            db=db, recorder=recorder, account_session=webhook_operator, task_id=str(run.id)
        )

        assert result.errors
        assert [error.message for error in result.errors] == ["Retry is unavailable: Delivery still in progress."]
        assert recorder.calls == []

    async def test_retry_of_a_delivery_requires_the_update_permission_on_the_webhook_kind(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, requester: AccountSession
    ) -> None:
        run = await self.create_run(prefect_client=prefect_client, flow=webhook_send, parameters=WEBHOOK_PARAMETERS)
        recorder = WorkflowRecorder()

        result = await self.run_mutation(db=db, recorder=recorder, account_session=requester, task_id=str(run.id))

        assert result.errors
        assert [error.message for error in result.errors] == [
            "You do not have the following permission: object:Core:StandardWebhook:update:allow_default"
        ]
        assert recorder.calls == []

    async def test_retry_of_a_task_type_without_recovery_actions_is_refused(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, requester: AccountSession
    ) -> None:
        run = await self.create_run(
            prefect_client=prefect_client, flow=dummy_flow, parameters={"firstname": "john", "lastname": "doe"}
        )
        recorder = WorkflowRecorder()

        result = await self.run_mutation(db=db, recorder=recorder, account_session=requester, task_id=str(run.id))

        assert result.errors
        assert [error.message for error in result.errors] == [
            "Retry is unavailable: it is not supported for this task."
        ]
        assert recorder.calls == []

    async def test_retry_of_a_task_that_no_longer_exists_is_refused(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, requester: AccountSession
    ) -> None:
        recorder = WorkflowRecorder()

        result = await self.run_mutation(db=db, recorder=recorder, account_session=requester, task_id=str(uuid4()))

        assert result.errors
        assert [error.message for error in result.errors] == ["This delivery is no longer available."]
        assert recorder.calls == []
