from graphene import Boolean, Field, List, ObjectType, String
from graphql import GraphQLResolveInfo  # pylint: disable=no-name-in-module

from .mutations import BranchCreate, BranchMerge, BranchRebase, BranchValidate
from .types import BranchDiffType, BranchType
from .utils import extract_fields

# pylint: disable=unused-argument


async def default_list_resolver(root, info: GraphQLResolveInfo, **kwargs):
    fields = await extract_fields(info.field_nodes[0].selection_set)
    return await info.return_type.of_type.graphene_type.get_list(**kwargs, fields=fields, context=info.context)


class InfrahubBaseQuery(ObjectType):
    branch = List(BranchType)

    diff = Field(
        BranchDiffType,
        branch=String(required=True, description="Name of the branch to use to calculate the diff."),
        time_from=String(required=False),
        time_to=String(required=False),
        branch_only=Boolean(required=False, default_value=False),
    )

    @staticmethod
    async def resolve_branch(root, info, **kwargs):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchType.get_list(fields=fields, context=info.context, **kwargs)

    @staticmethod
    async def resolve_diff(
        root, info, branch: str, branch_only: bool, time_from: str = None, time_to: str = None, **kwargs
    ):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchDiffType.get_diff(
            fields=fields,
            context=info.context,
            branch_only=branch_only,
            diff_from=time_from,
            diff_to=time_to,
            branch=branch,
        )


class InfrahubBaseMutation(ObjectType):
    branch_create = BranchCreate.Field()
    branch_rebase = BranchRebase.Field()
    branch_merge = BranchMerge.Field()
    branch_validate = BranchValidate.Field()
