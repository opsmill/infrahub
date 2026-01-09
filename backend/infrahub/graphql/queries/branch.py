from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import ID, Argument, Boolean, Field, Int, List, NonNull, String

from infrahub.constants.enums import OrderByField, OrderDirection
from infrahub.core.node.standard import StandardNodeOrdering, StandardNodeQueryFields
from infrahub.core.registry import registry
from infrahub.exceptions import ValidationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types import BranchType, InfrahubBranch, InfrahubBranchType
from infrahub.graphql.types.metadata import OrderInput

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo


def standard_node_ordering_from_order_input(order: OrderInput | None = None) -> StandardNodeOrdering:
    """Create a StandardNodeOrdering from an OrderInput.

    Args:
        order: Optional ordering specification from GraphQL input.

    Returns:
        StandardNodeOrdering with the specified field and direction, or defaults to ID with no direction.

    Raises:
        ValidationError: If both created_at and updated_at are specified.
    """
    if order is None or not order.node_metadata:
        return StandardNodeOrdering()

    created_at = getattr(order.node_metadata, "created_at", None)
    updated_at = getattr(order.node_metadata, "updated_at", None)

    if created_at and updated_at:
        raise ValidationError("Only one of 'created_at' or 'updated_at' can be specified for ordering.")

    if created_at:
        return StandardNodeOrdering(order_by=OrderByField.CREATED_AT, direction=OrderDirection(created_at.value))

    if updated_at:
        return StandardNodeOrdering(order_by=OrderByField.UPDATED_AT, direction=OrderDirection(updated_at.value))

    return StandardNodeOrdering()


async def branch_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    fields = extract_graphql_fields(info)
    return await BranchType.get_list(
        graphql_context=info.context, fields=StandardNodeQueryFields(node=fields), exclude_global=True, **kwargs
    )


BranchQueryList = Field(
    List(of_type=NonNull(BranchType)),
    ids=List(ID),
    name=String(),
    description="Retrieve information about active branches.",
    resolver=branch_resolver,
    required=True,
)


async def infrahub_branch_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    limit: int | None = None,
    offset: int | None = None,
    name__value: str | None = None,
    ids: list[str] | None = None,
    partial_match: bool = False,
    order: OrderInput | None = None,
) -> dict[str, Any]:
    if isinstance(limit, int) and limit < 1:
        raise ValidationError("limit must be >= 1")
    if isinstance(offset, int) and offset < 0:
        raise ValidationError("offset must be >= 0")

    node_ordering = standard_node_ordering_from_order_input(order)

    fields = extract_graphql_fields(info)
    result: dict[str, Any] = {}
    if "edges" in fields:
        query_fields = StandardNodeQueryFields(
            node=fields.get("edges", {}).get("node", {}),
            node_metadata=fields.get("edges", {}).get("node_metadata", {}),
        )
        branches = await InfrahubBranch.get_list(
            graphql_context=info.context,
            fields=query_fields,
            limit=limit,
            offset=offset,
            name=name__value,
            ids=ids,
            exclude_global=True,
            partial_match=partial_match,
            node_ordering=node_ordering,
        )
        result["edges"] = branches
    if "count" in fields:
        result["count"] = await InfrahubBranchType.get_list_count(
            graphql_context=info.context,
            name=name__value,
            ids=ids,
            partial_match=partial_match,
            node_ordering=node_ordering,
        )

    if "default_branch" in fields:
        default_branch = await InfrahubBranch.get_by_name(
            graphql_context=info.context,
            fields=fields["default_branch"],
            name=registry.default_branch,
        )
        result["default_branch"] = default_branch["node"]

    return result


InfrahubBranchQueryList = Field(
    InfrahubBranchType,
    offset=Int(),
    limit=Int(),
    name__value=String(),
    ids=List(ID),
    partial_match=Boolean(default_value=False),
    order=Argument(
        OrderInput,
        required=False,
        description="Define ordering of results for branch queries.",
    ),
    description="Retrieve paginated information about active branches.",
    resolver=infrahub_branch_resolver,
    required=True,
)
