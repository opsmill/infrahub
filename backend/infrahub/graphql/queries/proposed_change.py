from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from graphene import Boolean, Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericAccount, CoreProposedChange
from infrahub.proposed_change.constants import ProposedChangeState

if TYPE_CHECKING:
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


@dataclass
class ActionRule:
    action: str
    checks: list[Callable[[CoreProposedChange, GraphqlContext, CoreGenericAccount], str | None]]


def is_proposed_change_author(
    proposed_change: CoreProposedChange,  # noqa: ARG001
    graphql_context: GraphqlContext,
    proposed_change_author: CoreGenericAccount,
) -> str | None:
    if graphql_context.active_account_session.account_id != proposed_change_author.id:
        return "You are not the author of the proposed change"
    return None


def proposed_change_state_is(
    required: ProposedChangeState,
) -> Callable[[CoreProposedChange, GraphqlContext, CoreGenericAccount], str | None]:
    def check(
        proposed_change: CoreProposedChange,
        graphql_context: GraphqlContext,  # noqa: ARG001
        proposed_change_author: CoreGenericAccount,  # noqa: ARG001
    ) -> str | None:
        if proposed_change.state.value.value != required:
            return f"The proposed change state is not {required.value}"
        return None

    return check


def proposed_change_is_not_draft(
    proposed_change: CoreProposedChange,
    graphql_context: GraphqlContext,  # noqa: ARG001
    proposed_change_author: CoreGenericAccount,  # noqa: ARG001
) -> str | None:
    if proposed_change.is_draft.value:
        return "The proposed change is still marked as draft"
    return None


def account_has_permission(
    permission: GlobalPermission,
) -> Callable[[CoreProposedChange, GraphqlContext, CoreGenericAccount], str | None]:
    def check(
        proposed_change: CoreProposedChange,  # noqa: ARG001
        graphql_context: GraphqlContext,
        proposed_change_author: CoreGenericAccount,  # noqa: ARG001
    ) -> str | None:
        if not graphql_context.active_permissions.has_permission(permission=permission):
            return "You do not have the permission"
        return None

    return check


ACTION_RULES = [
    ActionRule("open", [proposed_change_state_is(ProposedChangeState.CLOSED)]),
    ActionRule("close", [proposed_change_state_is(ProposedChangeState.OPEN)]),
    ActionRule("change_draft_state", [is_proposed_change_author, proposed_change_state_is(ProposedChangeState.OPEN)]),
    ActionRule(
        "review",
        [proposed_change_state_is(ProposedChangeState.OPEN), account_has_permission(REVIEW_PROPOSED_CHANGE_PERMISSION)],
    ),
    ActionRule(
        "merge",
        [
            proposed_change_state_is(ProposedChangeState.OPEN),
            proposed_change_is_not_draft,
            account_has_permission(MERGE_PROPOSED_CHANGE_PERMISSION),
        ],
    ),
]


def get_available_actions(
    proposed_change: CoreProposedChange, graphql_context: GraphqlContext, proposed_change_author: CoreGenericAccount
) -> list[dict[str, str | bool | None]]:
    results: list[dict[str, str | bool | None]] = []
    for rule in ACTION_RULES:
        for check in rule.checks:
            reason = check(proposed_change, graphql_context, proposed_change_author)
            if reason:
                results.append({"action": rule.action, "available": False, "reason": reason})
                break
        else:
            results.append({"action": rule.action, "available": True, "reason": None})
    return results


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
        actions = get_available_actions(
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
                    node["unavailability_reason"] = action["reason"]

                nodes.append({"node": node})

            response["edges"] = nodes

        return response


ProposedChangeAvailableActions = Field(
    AvailableActions, proposed_change_id=String(required=True), resolver=AvailableActions.resolve, required=True
)
