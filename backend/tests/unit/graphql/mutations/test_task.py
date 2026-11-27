from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from prefect.client.schemas.objects import StateType

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.exceptions import PermissionDeniedError, ValidationError
from infrahub.graphql.mutations.task import (
    DeliveryActionAuthorizer,
    DeliveryRun,
    TaskRetryDispatcher,
    TaskRetryHandler,
    resolve_delivery_branch_name,
)
from infrahub.graphql.queries.task_actions import (
    CANCEL_IN_PROGRESS_REASON,
    RETRY_UNAVAILABLE_REASON,
    TaskActionGenerator,
    TaskActionType,
)
from infrahub.permissions.manager import PermissionManager
from infrahub.permissions.resolver import PermissionResolver
from infrahub.permissions.types import AssignedPermissions
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, WEBHOOK_SEND
from infrahub.workflows.models import WorkflowInfo

DEFAULT_BRANCH = "main"
OTHER_BRANCH = "feature"


def build_permission_manager(granted: list[ObjectPermission]) -> PermissionManager:
    return PermissionManager(
        account_session=AccountSession(account_id="account-1", auth_type=AuthType.API),
        resolver=PermissionResolver(
            permissions=AssignedPermissions(global_permissions=[], object_permissions=granted),
            default_branch_name=DEFAULT_BRANCH,
        ),
    )


def build_authorizer(branch_name: str, granted: list[ObjectPermission]) -> DeliveryActionAuthorizer:
    return DeliveryActionAuthorizer(
        action_generator=TaskActionGenerator(),
        permissions=build_permission_manager(granted=granted),
        branch_name=branch_name,
        default_branch_name=DEFAULT_BRANCH,
    )


def build_delivery(
    branch_name: str | None,
    webhook_kind: str = InfrahubKind.STANDARDWEBHOOK,
    state_type: StateType = StateType.COMPLETED,
) -> DeliveryRun:
    return DeliveryRun(
        workflow_name=WEBHOOK_SEND.name,
        state_type=state_type,
        branch_name=branch_name,
        parameters={"webhook_kind": webhook_kind},
    )


def webhook_update_grant(decision: PermissionDecision, name: str = "StandardWebhook") -> ObjectPermission:
    return ObjectPermission(namespace="Core", name=name, action=PermissionAction.UPDATE.value, decision=decision.value)


@dataclass
class ResolveBranchCase:
    name: str
    delivery_branch: str | None
    expected: str


RESOLVE_BRANCH_CASES = [
    ResolveBranchCase(name="delivery_branch_wins", delivery_branch=OTHER_BRANCH, expected=OTHER_BRANCH),
    ResolveBranchCase(name="branchless_delivery_belongs_to_default", delivery_branch=None, expected=DEFAULT_BRANCH),
]


@pytest.mark.parametrize("case", RESOLVE_BRANCH_CASES, ids=[case.name for case in RESOLVE_BRANCH_CASES])
def test_resolve_delivery_branch_name(case: ResolveBranchCase) -> None:
    delivery = build_delivery(branch_name=case.delivery_branch)
    assert resolve_delivery_branch_name(delivery=delivery, default_branch_name=DEFAULT_BRANCH) == case.expected


@dataclass
class BranchDecisionCase:
    name: str
    branch_name: str
    granted_decision: PermissionDecision
    required_decision: str | None


BRANCH_DECISION_CASES = [
    BranchDecisionCase(
        name="default_branch_allowed_with_default_grant",
        branch_name=DEFAULT_BRANCH,
        granted_decision=PermissionDecision.ALLOW_DEFAULT,
        required_decision=None,
    ),
    BranchDecisionCase(
        name="default_branch_denied_with_other_grant",
        branch_name=DEFAULT_BRANCH,
        granted_decision=PermissionDecision.ALLOW_OTHER,
        required_decision="allow_default",
    ),
    BranchDecisionCase(
        name="other_branch_allowed_with_other_grant",
        branch_name=OTHER_BRANCH,
        granted_decision=PermissionDecision.ALLOW_OTHER,
        required_decision=None,
    ),
    BranchDecisionCase(
        name="other_branch_denied_with_default_grant",
        branch_name=OTHER_BRANCH,
        granted_decision=PermissionDecision.ALLOW_DEFAULT,
        required_decision="allow_other",
    ),
    BranchDecisionCase(
        name="other_branch_allowed_with_all_grant",
        branch_name=OTHER_BRANCH,
        granted_decision=PermissionDecision.ALLOW_ALL,
        required_decision=None,
    ),
]


@pytest.mark.parametrize("case", BRANCH_DECISION_CASES, ids=[case.name for case in BRANCH_DECISION_CASES])
def test_authorize_follows_the_scoped_branch(case: BranchDecisionCase) -> None:
    delivery = build_delivery(branch_name=case.branch_name)
    authorizer = build_authorizer(
        branch_name=case.branch_name, granted=[webhook_update_grant(decision=case.granted_decision)]
    )

    if case.required_decision is None:
        authorizer.authorize(delivery=delivery, action=TaskActionType.RETRY)
    else:
        with pytest.raises(
            PermissionDeniedError,
            match=rf"^You do not have the following permission: "
            rf"object:Core:StandardWebhook:update:{case.required_decision}$",
        ):
            authorizer.authorize(delivery=delivery, action=TaskActionType.RETRY)


def test_authorize_requires_the_permission_of_the_delivered_webhook_kind() -> None:
    delivery = build_delivery(branch_name=DEFAULT_BRANCH, webhook_kind=InfrahubKind.CUSTOMWEBHOOK)
    authorizer = build_authorizer(
        branch_name=DEFAULT_BRANCH, granted=[webhook_update_grant(decision=PermissionDecision.ALLOW_ALL)]
    )

    with pytest.raises(
        PermissionDeniedError,
        match=r"^You do not have the following permission: object:Core:CustomWebhook:update:allow_default$",
    ):
        authorizer.authorize(delivery=delivery, action=TaskActionType.RETRY)


def test_authorize_rejects_an_unavailable_action_before_checking_permissions() -> None:
    delivery = build_delivery(branch_name=DEFAULT_BRANCH, state_type=StateType.RUNNING)
    authorizer = build_authorizer(branch_name=DEFAULT_BRANCH, granted=[])

    with pytest.raises(ValidationError, match=rf"^Retry is unavailable: {RETRY_UNAVAILABLE_REASON}\.$"):
        authorizer.authorize(delivery=delivery, action=TaskActionType.RETRY)


def test_authorize_rejects_cancelling_a_delivery_already_being_cancelled() -> None:
    delivery = build_delivery(branch_name=DEFAULT_BRANCH, state_type=StateType.CANCELLING)
    authorizer = build_authorizer(branch_name=DEFAULT_BRANCH, granted=[])

    with pytest.raises(ValidationError, match=rf"^Cancel is unavailable: {CANCEL_IN_PROGRESS_REASON}\.$"):
        authorizer.authorize(delivery=delivery, action=TaskActionType.CANCEL)


class RecordingRetryHandler(TaskRetryHandler):
    """Records the runs it is asked to retry, for the runs of one workflow."""

    def __init__(self, workflow_name: str) -> None:
        self.workflow_name = workflow_name
        self.submitted = WorkflowInfo(id=uuid4())
        self.retried: list[DeliveryRun] = []

    def supports(self, run: DeliveryRun) -> bool:
        return run.workflow_name == self.workflow_name

    async def retry(self, run: DeliveryRun) -> WorkflowInfo | None:
        self.retried.append(run)
        return self.submitted


def build_run(workflow_name: str, state_type: StateType = StateType.COMPLETED) -> DeliveryRun:
    return DeliveryRun(workflow_name=workflow_name, state_type=state_type, branch_name="main", parameters={})


async def test_retry_goes_to_the_handler_of_the_task_type_only() -> None:
    delivery_handler = RecordingRetryHandler(workflow_name=WEBHOOK_SEND.name)
    artifact_handler = RecordingRetryHandler(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)
    dispatcher = TaskRetryDispatcher(
        action_generator=TaskActionGenerator(), handlers=[delivery_handler, artifact_handler]
    )
    run = build_run(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)

    submitted = await dispatcher.retry(run=run)

    assert submitted == artifact_handler.submitted
    assert artifact_handler.retried == [run]
    assert delivery_handler.retried == []


async def test_retry_that_does_not_apply_to_the_state_of_the_run_reaches_no_handler() -> None:
    artifact_handler = RecordingRetryHandler(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)
    dispatcher = TaskRetryDispatcher(action_generator=TaskActionGenerator(), handlers=[artifact_handler])
    run = build_run(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name, state_type=StateType.RUNNING)

    with pytest.raises(ValidationError, match=r"^Retry is unavailable: Artifact check still in progress\.$"):
        await dispatcher.retry(run=run)

    assert artifact_handler.retried == []


async def test_retry_of_a_retryable_task_type_without_a_handler_is_refused() -> None:
    delivery_handler = RecordingRetryHandler(workflow_name=WEBHOOK_SEND.name)
    dispatcher = TaskRetryDispatcher(action_generator=TaskActionGenerator(), handlers=[delivery_handler])
    run = build_run(workflow_name=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name)

    with pytest.raises(ValidationError, match=r"^Retry is unavailable: it is not supported for this task\.$"):
        await dispatcher.retry(run=run)

    assert delivery_handler.retried == []
