from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericAccount, CoreProposedChange
from infrahub.exceptions import ValidationError
from infrahub.proposed_change.constants import ProposedChangeAction, ProposedChangeState

if TYPE_CHECKING:
    from collections.abc import Sequence

    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


MERGE_PROPOSED_CHANGE_PERMISSION = GlobalPermission(
    action=GlobalPermissions.MERGE_PROPOSED_CHANGE.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)
REVIEW_PROPOSED_CHANGE_PERMISSION = GlobalPermission(
    action=GlobalPermissions.REVIEW_PROPOSED_CHANGE.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)


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


ACTION_RULES = [
    ActionRule(
        action=ProposedChangeAction.OPEN,
        checks=[StateIs(expected_states=[ProposedChangeState.CLOSED, ProposedChangeState.CANCELED])],
    ),
    ActionRule(action=ProposedChangeAction.CLOSE, checks=[StateIs(expected_states=[ProposedChangeState.OPEN])]),
    ActionRule(
        action=ProposedChangeAction.SET_DRAFT,
        checks=[IsAuthor(), StateIs(expected_states=[ProposedChangeState.OPEN]), DraftIs(expected=False)],
    ),
    ActionRule(
        action=ProposedChangeAction.UNSET_DRAFT,
        checks=[IsAuthor(), StateIs(expected_states=[ProposedChangeState.OPEN]), DraftIs(expected=True)],
    ),
    ActionRule(
        action=ProposedChangeAction.REVIEW,
        checks=[
            StateIs(expected_states=[ProposedChangeState.OPEN]),
            HasPermission(permission=REVIEW_PROPOSED_CHANGE_PERMISSION),
        ],
    ),
    ActionRule(
        action=ProposedChangeAction.MERGE,
        checks=[
            StateIs(expected_states=[ProposedChangeState.OPEN]),
            DraftIs(expected=False),
            HasPermission(permission=MERGE_PROPOSED_CHANGE_PERMISSION),
        ],
    ),
]


class ActionAvailability(ObjectType):
    action = Field(String, required=True, description="The action that a user may want to take on a proposed change")
    available = Field(Boolean, required=True, description="Tells if the action is available")
    unavailability_reason = Field(String, required=False, description="The reason why an action may be unavailable")


class ActionAvailabilityEdge(ObjectType):
    node = Field(ActionAvailability, required=True)


class AvailableActions(ObjectType):
    count = Field(Int, required=True, description="The number of allocations within the selected pool.")
    edges = Field(List(of_type=NonNull(ActionAvailabilityEdge), required=True), required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        proposed_change_id: str,
    ) -> dict:
        graphql_context: GraphqlContext = info.context
        proposed_change = await NodeManager.get_one(
            kind=CoreProposedChange,
            id=proposed_change_id,
            db=graphql_context.db,
            branch=graphql_context.branch,
            raise_on_error=True,
        )
        proposed_change_author = await proposed_change.created_by.get_peer(
            db=graphql_context.db, peer_type=CoreGenericAccount, raise_on_error=True
        )
        actions = ActionRulesEvaluator(rules=ACTION_RULES).evaluate(
            proposed_change=proposed_change,
            graphql_context=graphql_context,
            proposed_change_author=proposed_change_author,
        )

        fields = await extract_fields_first_node(info=info)
        response: dict[str, Any] = {}

        if "count" in fields:
            response["count"] = len(actions)

        if edges := fields.get("edges"):
            node_fields = edges.get("node", {})

            nodes = []
            for action in actions:
                node = {}

                if "action" in node_fields:
                    node["action"] = action["action"]
                if "available" in node_fields:
                    node["available"] = action["available"]
                if "unavailability_reason" in node_fields:
                    node["unavailability_reason"] = action["unavailability_reason"]

                nodes.append({"node": node})

            response["edges"] = nodes

        return response


ProposedChangeAvailableActions = Field(
    AvailableActions, proposed_change_id=String(required=True), resolver=AvailableActions.resolve, required=True
)
