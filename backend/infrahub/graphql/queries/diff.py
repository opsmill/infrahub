from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Union
from typing import List as TypingList

from graphene import Boolean, Field, List, ObjectType, String

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch.branch import Branch
    from infrahub.database import InfrahubDatabase


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
    ):
        return await DiffSummaryEntry.get_summary(
            context=info.context,
            branch_only=branch_only,
            time_from=time_from or None,
            time_to=time_to or None,
        )

    @classmethod
    async def get_summary(
        cls,
        context: Dict[str, Any],
        branch_only: bool,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> TypingList[Dict[str, Union[str, TypingList[str]]]]:
        db: InfrahubDatabase = context.get("infrahub_database")
        branch: Branch = context.get("infrahub_branch")
        diff = await branch.diff(db=db, diff_from=time_from, diff_to=time_to, branch_only=branch_only)
        summary = await diff.get_summary(db=db)
        return [entry.to_graphql() for entry in summary]


DiffSummary = Field(
    List(DiffSummaryEntry),
    time_from=String(required=False),
    time_to=String(required=False),
    branch_only=Boolean(required=False, default_value=False),
    resolver=DiffSummaryEntry.resolve,
)
