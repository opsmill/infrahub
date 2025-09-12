from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.exceptions import ValidationError

from .checker import verify_proposed_change_is_mergeable
from .constants import ProposedChangeAction, ProposedChangeState

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.protocols import CoreGenericAccount, CoreProposedChange
    from infrahub.graphql.initialization import GraphqlContext


class Check(ABC):
    @abstractmethod
    async def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> None: ...


class IsAuthor(Check):
    async def evaluate(
        self,
        proposed_change: CoreProposedChange,  # noqa: ARG002
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> None:
        if proposed_change_author.id != graphql_context.active_account_session.account_id:
            raise ValidationError("You are not the author of the proposed change")


class StateIs(Check):
    def __init__(self, expected: Sequence[ProposedChangeState]) -> None:
        self.expected = expected

    async def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,  # noqa: ARG002
        graphql_context: GraphqlContext,  # noqa: ARG002
    ) -> None:
        if proposed_change.state.value.value not in self.expected:
            raise ValidationError(f"The proposed change is not {', '.join([i.value for i in self.expected])}")


class DraftIs(Check):
    def __init__(self, expected: bool) -> None:
        self.expected = expected

    async def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,  # noqa: ARG002
        graphql_context: GraphqlContext,  # noqa: ARG002
    ) -> None:
        if proposed_change.is_draft.value != self.expected:
            if self.expected:
                raise ValidationError("The proposed change is not a draft")
            raise ValidationError("The proposed change is a draft")


class HasPermission(Check):
    def __init__(self, permission: GlobalPermission) -> None:
        self.permission = permission

    async def evaluate(
        self,
        proposed_change: CoreProposedChange,  # noqa: ARG002
        proposed_change_author: CoreGenericAccount,  # noqa: ARG002
        graphql_context: GraphqlContext,
    ) -> None:
        if not graphql_context.active_permissions.has_permission(permission=self.permission):
            raise ValidationError("You do not have the permission to perform this action")


class IsMergeable(Check):
    async def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,  # noqa: ARG002
        graphql_context: GraphqlContext,
    ) -> None:
        try:
            await verify_proposed_change_is_mergeable(
                proposed_change=proposed_change,  # type: ignore[arg-type]
                db=graphql_context.db,
                account_session=graphql_context.active_account_session,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc


@dataclass
class ActionRule:
    action: ProposedChangeAction
    checks: list[Check]

    async def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> dict[str, str | bool | None]:
        for check in self.checks:
            try:
                await check.evaluate(
                    proposed_change=proposed_change,
                    proposed_change_author=proposed_change_author,
                    graphql_context=graphql_context,
                )
            except ValidationError as exc:
                return {"action": self.action.value, "available": False, "unavailability_reason": exc.message}

        return {"action": self.action.value, "available": True, "unavailability_reason": None}


class ActionRulesEvaluator:
    def __init__(self, rules: list[ActionRule]):
        self.rules = rules

    async def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> list[dict[str, str | bool | None]]:
        report: list[dict[str, str | bool | None]] = []
        for rule in self.rules:
            report.append(
                await rule.evaluate(
                    proposed_change=proposed_change,
                    proposed_change_author=proposed_change_author,
                    graphql_context=graphql_context,
                )
            )
        return report


MERGE_PROPOSED_CHANGE_PERMISSION = GlobalPermission(
    action=GlobalPermissions.MERGE_PROPOSED_CHANGE.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)
REVIEW_PROPOSED_CHANGE_PERMISSION = GlobalPermission(
    action=GlobalPermissions.REVIEW_PROPOSED_CHANGE.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)

ACTION_RULES = [
    ActionRule(action=ProposedChangeAction.OPEN, checks=[StateIs(expected=[ProposedChangeState.CLOSED])]),
    ActionRule(action=ProposedChangeAction.CLOSE, checks=[StateIs(expected=[ProposedChangeState.OPEN])]),
    ActionRule(
        action=ProposedChangeAction.SET_DRAFT,
        checks=[IsAuthor(), StateIs(expected=[ProposedChangeState.OPEN]), DraftIs(expected=False)],
    ),
    ActionRule(
        action=ProposedChangeAction.UNSET_DRAFT,
        checks=[IsAuthor(), StateIs(expected=[ProposedChangeState.OPEN]), DraftIs(expected=True)],
    ),
    ActionRule(
        action=ProposedChangeAction.APPROVE,
        checks=[
            StateIs(expected=[ProposedChangeState.OPEN]),
            HasPermission(permission=REVIEW_PROPOSED_CHANGE_PERMISSION),
        ],
    ),
    ActionRule(
        action=ProposedChangeAction.CANCEL_APPROVE,
        checks=[
            StateIs(expected=[ProposedChangeState.OPEN]),
            HasPermission(permission=REVIEW_PROPOSED_CHANGE_PERMISSION),
        ],
    ),
    ActionRule(
        action=ProposedChangeAction.REJECT,
        checks=[
            StateIs(expected=[ProposedChangeState.OPEN]),
            HasPermission(permission=REVIEW_PROPOSED_CHANGE_PERMISSION),
        ],
    ),
    ActionRule(
        action=ProposedChangeAction.CANCEL_REJECT,
        checks=[
            StateIs(expected=[ProposedChangeState.OPEN]),
            HasPermission(permission=REVIEW_PROPOSED_CHANGE_PERMISSION),
        ],
    ),
    ActionRule(
        action=ProposedChangeAction.MERGE,
        checks=[
            StateIs(expected=[ProposedChangeState.OPEN]),
            DraftIs(expected=False),
            HasPermission(permission=MERGE_PROPOSED_CHANGE_PERMISSION),
            IsMergeable(),
        ],
    ),
]
