from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericAccount, CoreProposedChange
from infrahub.proposed_change.action_checker import ACTION_RULES, ActionRulesEvaluator

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class ActionAvailability(ObjectType):
    action = Field(String, required=True, description="The action that a user may want to take on a proposed change")
    available = Field(Boolean, required=True, description="Tells if the action is available")
    unavailability_reason = Field(String, required=False, description="The reason why an action may be unavailable")


class ActionAvailabilityEdge(ObjectType):
    node = Field(ActionAvailability, required=True)


class AvailableActions(ObjectType):
    count = Field(Int, required=True, description="The number of available actions for the proposed change.")
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
        actions = await ActionRulesEvaluator(rules=ACTION_RULES).evaluate(
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
