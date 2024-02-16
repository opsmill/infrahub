from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Union

from dependencies.registry import get_component_registry
from graphene import Boolean, Field, List, ObjectType, String

from infrahub.core.diff import BranchDiffer
from infrahub.core.to_graphql.aggregated import AggregatedToGraphQLTranslators
from infrahub.core.to_graphql.model import ToGraphQLRequest

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext


class DiffSummaryEntry(ObjectType):
    branch = String(required=True)
    node = String(required=True)
    kind = String(required=True)
    actions = List(String, required=True)

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
        to_graphql_translator = get_component_registry().get_component(AggregatedToGraphQLTranslators)

        diff = await BranchDiffer.init(
            db=context.db, branch=context.branch, diff_from=time_from, diff_to=time_to, branch_only=branch_only
        )
        summary = await diff.get_summary(db=context.db)
        return [await to_graphql_translator.to_graphql(ToGraphQLRequest(obj=entry, db=context.db)) for entry in summary]


DiffSummary = Field(
    List(DiffSummaryEntry),
    time_from=String(required=False),
    time_to=String(required=False),
    branch_only=Boolean(required=False, default_value=False),
    resolver=DiffSummaryEntry.resolve,
)
