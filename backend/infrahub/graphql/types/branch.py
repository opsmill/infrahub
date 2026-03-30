from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, Int, List, NonNull, ObjectType, String

from infrahub.core.branch import Branch
from infrahub.core.branch.filters import BranchListFilters
from infrahub.core.node.standard import StandardNodeQueryFields

from ...exceptions import BranchNotFoundError
from .enums import InfrahubBranchStatus
from .metadata import InfrahubStandardNodeMetaData
from .standard_node import InfrahubObjectType

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext


class BranchType(InfrahubObjectType):
    id = String(required=True)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    status = InfrahubBranchStatus(required=True)
    graph_version = Int(required=False)
    created_at = String(required=False)
    sync_with_git = Boolean(required=False)
    is_default = Boolean(required=False)
    is_isolated = Field(Boolean(required=False), deprecation_reason="non isolated mode is not supported anymore")
    has_schema_changes = Boolean(required=False)

    class Meta:
        description = "Branch"
        name = "Branch"
        model = Branch

    @classmethod
    async def get_list(
        cls,
        fields: StandardNodeQueryFields,
        graphql_context: GraphqlContext,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        async with graphql_context.db.start_session(read_only=True) as db:
            objs = await Branch.get_list(db=db, **kwargs)
            return [await obj.to_graphql_flat(fields=fields.node) for obj in objs]


class RequiredStringValueField(ObjectType):
    value = String(required=True)


class NonRequiredStringValueField(ObjectType):
    value = String(required=False)


class NonRequiredIntValueField(ObjectType):
    value = Int(required=False)


class NonRequiredBooleanValueField(ObjectType):
    value = Boolean(required=False)


class StatusField(ObjectType):
    value = InfrahubBranchStatus(required=True)


class InfrahubBranch(BranchType):
    name = Field(RequiredStringValueField, required=True)
    description = Field(NonRequiredStringValueField, required=False)
    origin_branch = Field(NonRequiredStringValueField, required=False)
    branched_from = Field(NonRequiredStringValueField, required=False)
    graph_version = Field(NonRequiredIntValueField, required=False)
    status = Field(StatusField, required=True)
    sync_with_git = Field(NonRequiredBooleanValueField, required=False)
    is_default = Field(NonRequiredBooleanValueField, required=False)
    is_isolated = Field(
        NonRequiredBooleanValueField, required=False, deprecation_reason="non isolated mode is not supported anymore"
    )
    has_schema_changes = Field(NonRequiredBooleanValueField, required=False)

    @classmethod
    async def get_list(
        cls,
        fields: StandardNodeQueryFields,
        graphql_context: GraphqlContext,
        branch_filters: BranchListFilters | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        kwargs["branch_filters"] = branch_filters
        async with graphql_context.db.start_session(read_only=True) as db:
            objs = await Branch.get_list(db=db, **kwargs)
            return [await obj.to_graphql(fields=fields) for obj in objs]

    @classmethod
    async def get_by_name(
        cls,
        fields: dict,
        graphql_context: GraphqlContext,
        name: str,
    ) -> dict[str, Any]:
        branch_filters = BranchListFilters(name=name)
        branch_responses = await cls.get_list(
            fields=StandardNodeQueryFields(node=fields), graphql_context=graphql_context, branch_filters=branch_filters
        )

        if branch_responses:
            return branch_responses[0]
        raise BranchNotFoundError(f"Branch with name '{name}' not found")

    class Meta:
        description = "InfrahubBranch"
        name = "InfrahubBranch"


class InfrahubBranchEdge(ObjectType):
    node = Field(InfrahubBranch, required=True)
    node_metadata = Field(InfrahubStandardNodeMetaData, required=True)


class InfrahubBranchType(ObjectType):
    count = Field(Int, description="Total number of items")
    edges = Field(NonNull(List(of_type=NonNull(InfrahubBranchEdge))))
    default_branch = Field(
        InfrahubBranch,
        required=True,
        description="The default branch of the Infrahub instance, provides a direct way to access the default branch regardless of filters.",
    )

    @classmethod
    async def get_list_count(
        cls,
        graphql_context: GraphqlContext,
        branch_filters: BranchListFilters | None = None,
        **kwargs: Any,
    ) -> int:
        async with graphql_context.db.start_session(read_only=True) as db:
            return await Branch.get_list_count(db=db, branch_filters=branch_filters, **kwargs)
