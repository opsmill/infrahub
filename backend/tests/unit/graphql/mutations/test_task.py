from __future__ import annotations

from dataclasses import dataclass

import pytest
from prefect.client.schemas.objects import StateType

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.exceptions import PermissionDeniedError, ValidationError
from infrahub.graphql.mutations.task import DeliveryActionAuthorizer, DeliveryRun, resolve_delivery_branch_name
from infrahub.graphql.queries.task_actions import RETRY_UNAVAILABLE_REASON, TaskActionGenerator, TaskActionType
from infrahub.permissions.manager import PermissionManager
from infrahub.permissions.resolver import PermissionResolver
from infrahub.permissions.types import AssignedPermissions
from infrahub.workflows.catalogue import WEBHOOK_SEND

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
