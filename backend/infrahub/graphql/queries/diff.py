from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Union

from graphene import Boolean, Field, JSONString, List, ObjectType, String

from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.payload_builder import DiffPayloadBuilder

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext


class DiffSummaryEntry(ObjectType):
    branch = String(required=True)
    node = String(required=True)
    id = String(required=True)
    kind = String(required=True)
    actions = List(String, required=True)
    action = String(required=True)
    display_label = String()
    elements = JSONString()

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        branch_only: bool,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> list[Dict[str, Union[str, list[str]]]]:
        return await DiffSummaryEntry.get_summary(
            info=info,
            branch_only=branch_only,
            time_from=time_from or None,
            time_to=time_to or None,
        )

    @classmethod
    async def get_summary(
        cls,
        info: GraphQLResolveInfo,
        branch_only: bool,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> list[Dict[str, Union[str, list[str]]]]:
        context: GraphqlContext = info.context
        diff = await BranchDiffer.init(
            db=context.db, branch=context.branch, diff_from=time_from, diff_to=time_to, branch_only=branch_only
        )
        diff_payload_builder = DiffPayloadBuilder(db=context.db, diff=diff)
        enriched_summaries = await diff_payload_builder.get_summarized_node_diffs()
        return [summary.to_graphql() for summary in enriched_summaries]


DiffSummary = Field(
    List(DiffSummaryEntry),
    time_from=String(required=False),
    time_to=String(required=False),
    branch_only=Boolean(required=False, default_value=False),
    resolver=DiffSummaryEntry.resolve,
)
