from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.account import GlobalPermission
    from infrahub.core.protocols import CoreGenericAccount, CoreProposedChange
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.proposed_change.constants import ProposedChangeAction, ProposedChangeState


class Check(ABC):
    @abstractmethod
    def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> None: ...


class IsAuthor(Check):
    def evaluate(
        self,
        proposed_change: CoreProposedChange,  # noqa: ARG002
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> None:
        if proposed_change_author.id != graphql_context.active_account_session.account_id:
            raise ValidationError("You are not the author of the proposed change")


class StateIs(Check):
    def __init__(self, expected_states: Sequence[ProposedChangeState]) -> None:
        self.expected_states = expected_states

    def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,  # noqa: ARG002
        graphql_context: GraphqlContext,  # noqa: ARG002
    ) -> None:
        if proposed_change.state.value.value not in self.expected_states:
            raise ValidationError(f"The proposed change is not {', '.join([i.value for i in self.expected_states])}")


class DraftIs(Check):
    def __init__(self, expected: bool) -> None:
        self.expected = expected

    def evaluate(
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

    def evaluate(
        self,
        proposed_change: CoreProposedChange,  # noqa: ARG002
        proposed_change_author: CoreGenericAccount,  # noqa: ARG002
        graphql_context: GraphqlContext,
    ) -> None:
        if not graphql_context.active_permissions.has_permission(permission=self.permission):
            raise ValidationError("You do not have the permission to perform this action")


@dataclass
class ActionRule:
    action: ProposedChangeAction
    checks: list[Check]

    def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> dict[str, str | bool | None]:
        for check in self.checks:
            try:
                check.evaluate(
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

    def evaluate(
        self,
        proposed_change: CoreProposedChange,
        proposed_change_author: CoreGenericAccount,
        graphql_context: GraphqlContext,
    ) -> list[dict[str, str | bool | None]]:
        report: list[dict[str, str | bool | None]] = []
        for rule in self.rules:
            report.append(
                rule.evaluate(
                    proposed_change=proposed_change,
                    proposed_change_author=proposed_change_author,
                    graphql_context=graphql_context,
                )
            )
        return report
