from graphene import Field, List, ObjectType, String
from graphql import GraphQLResolveInfo

from .mutations import BranchCreate, BranchMerge, BranchRebase, BranchValidate
from .types import BranchDiffType, BranchType
from .utils import extract_fields


async def default_list_resolver(root, info: GraphQLResolveInfo, **kwargs):

    fields = await extract_fields(info.field_nodes[0].selection_set)
    return await info.return_type.of_type.graphene_type.get_list(**kwargs, fields=fields, context=info.context)


class InfrahubBaseQuery(ObjectType):

    branch = List(BranchType)

    diff = Field(BranchDiffType, branch=String(required=True))

    async def resolve_branch(self, info, **kwargs):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchType.get_list(fields=fields, context=info.context, **kwargs)

    async def resolve_diff(root, info, branch, **kwargs):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchDiffType.get_diff(fields=fields, context=info.context, branch=branch)


class InfrahubBaseMutation(ObjectType):

    branch_create = BranchCreate.Field()
    branch_rebase = BranchRebase.Field()
    branch_merge = BranchMerge.Field()
    branch_validate = BranchValidate.Field()
