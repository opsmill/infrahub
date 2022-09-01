from graphene import Boolean, DateTime, Field, Int, List, ObjectType, Schema, String

from .mutations import BranchCreate, BranchMerge, BranchRebase, BranchValidate
from .query import BranchDiffType, BranchType
from .utils import extract_fields


async def default_list_resolver(root, info, **kwargs):

    fields = extract_fields(info.field_nodes[0].selection_set)
    return await info.return_type.of_type.graphene_type.get_list(**kwargs, fields=fields, context=info.context)


class InfrahubBaseQuery(ObjectType):

    branch = List(BranchType)

    diff = Field(BranchDiffType, branch=String(required=True))

    async def resolve_branch(self, info, **kwargs):
        fields = extract_fields(info.field_nodes[0].selection_set)
        return await BranchType.get_list(fields=fields, **kwargs)

    async def resolve_diff(root, info, branch, **kwargs):
        fields = extract_fields(info.field_nodes[0].selection_set)
        return await BranchDiffType.get_diff(fields=fields, branch=branch)


class InfrahubBaseMutation(ObjectType):

    branch_create = BranchCreate.Field()
    branch_rebase = BranchRebase.Field()
    branch_merge = BranchMerge.Field()
    branch_validate = BranchValidate.Field()
