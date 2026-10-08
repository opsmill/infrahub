from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import BigInt, Field, Float, InputObjectType, Int, List, NonNull, ObjectType, String

from infrahub.graphql.types.enums import PoolRecordProvenance as PoolRecordProvenanceType
from infrahub.pools.number_pool_mock import (
    DivisionFilterEntry,
    MockAllocations,
    MockDivisions,
    MockUtilization,
    get_allocations,
    get_divisions,
    get_utilization,
)

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.constants import PoolRecordProvenance
    from infrahub.graphql.initialization import GraphqlContext


def _division_filter(division: list[dict[str, str]] | None) -> list[DivisionFilterEntry] | None:
    if division is None:
        return None
    return [DivisionFilterEntry(path=entry["path"], value=entry["value"]) for entry in division]


class NumberPoolUtilizationFigures(ObjectType):
    class Meta:
        description = "Absolute and relative utilization of a pool, a range or a division."

    size = Field(
        BigInt,
        required=True,
        description="Number of values the pool, range or division can allocate. 0 when the pool has no range.",
    )
    used = Field(
        BigInt,
        required=True,
        description="Number of these values in use on any branch. A value used on several branches counts once.",
    )
    used_default_branch = Field(
        BigInt, required=True, description="Number of these values in use on the default branch."
    )
    used_branches = Field(
        BigInt,
        required=True,
        description="Number of these values in use only on other branches, not on the default branch.",
    )
    utilization = Field(Float, required=True, description="used as a percentage of size. 0 when size is 0.")
    utilization_default_branch = Field(
        Float, required=True, description="used_default_branch as a percentage of size. 0 when size is 0."
    )
    utilization_branches = Field(
        Float, required=True, description="used_branches as a percentage of size. 0 when size is 0."
    )


class NumberPoolScopeElement(ObjectType):
    class Meta:
        description = "One element of a pool's allocation scope."

    id = Field(
        String,
        required=True,
        description="The schema element id of the attribute or relationship, on the default branch.",
    )
    name = Field(String, required=True, description="The element's name, as currently declared on the default branch.")


class NumberPoolRangeUtilization(ObjectType):
    class Meta:
        description = "One range of a number pool with its own figures."

    id = Field(String, required=True, description="The range node's id.")
    display_label = Field(String, required=True, description="The range node's display label.")
    start = Field(BigInt, required=True, description="First value of the range, included.")
    end = Field(BigInt, required=True, description="Last value of the range, included.")
    weight = Field(BigInt, required=True, description="The range's allocation weight. 0 when the range declares none.")
    figures = Field(
        NumberPoolUtilizationFigures,
        required=True,
        description=(
            "Figures over the range's values. On a scoped pool, only the values held in the division passed in "
            "the division argument."
        ),
    )


class NumberPoolUtilization(ObjectType):
    class Meta:
        description = (
            "Utilization of one number pool and of each of its ranges. For a number pool, prefer this over "
            "InfrahubResourcePoolUtilization."
        )

    id = Field(String, required=True, description="The pool's id, as given in pool_id.")
    display_label = Field(String, required=True, description="The pool's display label.")
    allocation_scope = Field(
        List(NonNull(NumberPoolScopeElement)),
        required=True,
        description="The pool's allocation scope, in scope order. Empty for an unscoped pool.",
    )
    figures = Field(
        NumberPoolUtilizationFigures,
        required=True,
        description=(
            "Figures over all the values the pool can allocate. On a scoped pool, only the values held in the division passed "
            "in the division argument, which is required."
        ),
    )
    ranges = Field(
        List(NonNull(NumberPoolRangeUtilization)),
        required=True,
        description="The pool's ranges ordered by start, each with its own figures.",
    )

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        pool_id: str,
        division: list[dict[str, str]] | None = None,
    ) -> MockUtilization:
        graphql_context: GraphqlContext = info.context
        return get_utilization(
            pool_id=pool_id, request_branch=graphql_context.branch.name, division=_division_filter(division)
        )


class NumberPoolDivisionEntry(ObjectType):
    class Meta:
        description = "The value one scope element takes in a division."

    id = Field(String, required=True, description="The schema element id of the scope element.")
    path = Field(String, required=True, description='The scope element\'s name ("site", "role").')
    value = Field(
        String,
        required=True,
        description=(
            "Relationship element: the peer's id. Attribute element: the value as text. A holder holding nothing "
            "for the element: an empty string."
        ),
    )
    display_label = Field(
        String,
        required=True,
        description=(
            "Relationship element: the peer's display label, read on any branch, falling back to the peer's id "
            "when the peer cannot be read. Attribute element: the value as text."
        ),
    )
    peer_kind = Field(
        String,
        required=False,
        description="Relationship element: the peer's kind when the peer can be read. Otherwise null.",
    )


class NumberPoolDivisionEntryInput(InputObjectType):
    class Meta:
        description = "One entry of a division filter. Mirrors NumberPoolDivisionEntry."

    path = String(required=True, description="A scope element's name.")
    value = String(
        required=True, description="Relationship element: the peer's id. Attribute element: the value as text."
    )


class NumberPoolDivision(ObjectType):
    class Meta:
        description = "One division: a tuple of values of the scope."

    display_label = Field(
        String,
        required=True,
        description='The entries\' display labels joined with " / ".',
    )
    entries = Field(
        List(NonNull(NumberPoolDivisionEntry)),
        required=True,
        description="One entry per scope element, in scope order.",
    )
    figures = Field(
        NumberPoolUtilizationFigures,
        required=True,
        description="Figures for this division, over all the values the pool can allocate.",
    )


class NumberPoolDivisions(ObjectType):
    class Meta:
        description = "The divisions of one number pool, each with its figures."

    count = Field(Int, required=True, description="Number of divisions listed.")
    allocation_scope = Field(
        List(NonNull(NumberPoolScopeElement)),
        required=True,
        description="The pool's allocation scope, in scope order.",
    )
    divisions = Field(
        List(NonNull(NumberPoolDivision)),
        required=True,
        description=(
            "Every division holding at least one value the pool tracks on any live branch, the division of each "
            "holder read on the request's branch, ordered by utilization descending then by display_label. "
            "Empty for an unscoped pool."
        ),
    )

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        pool_id: str,
    ) -> MockDivisions:
        graphql_context: GraphqlContext = info.context
        return get_divisions(pool_id=pool_id, request_branch=graphql_context.branch.name)


class NumberPoolHolder(ObjectType):
    class Meta:
        description = "The node holding a tracked number."

    id = Field(String, required=True)
    hfid = Field(List(NonNull(String)), description="The holder's human-friendly id. Null when its kind declares none.")
    kind = Field(String, required=True)
    display_label = Field(String, required=True)


class NumberPoolRangeRef(ObjectType):
    class Meta:
        description = "A reference to one range of the pool."

    id = Field(String, required=True)
    display_label = Field(String, required=True)


class NumberPoolAllocation(ObjectType):
    class Meta:
        description = "One tracked number as held on one branch: one row per (record, branch-resolved value)."

    value = Field(BigInt, required=True, description="The number held.")
    branch = Field(String, required=True, description="The branch on which the holder's attribute holds this value.")
    holder = Field(
        NumberPoolHolder,
        required=True,
        description="The node whose attribute holds the value, read on the row's branch.",
    )
    identifier = Field(String, description="The identifier given when the number was allocated, if any.")
    provenance = Field(
        PoolRecordProvenanceType,
        required=True,
        description="ALLOCATED when the pool picked the number, PROVIDED when a user gave it.",
    )
    range = Field(NumberPoolRangeRef, required=True, description="The range whose bounds hold the value.")


class NumberPoolAllocations(ObjectType):
    class Meta:
        description = "A page of the numbers a pool tracks."

    count = Field(BigInt, required=True, description="Number of rows matching the filters, before offset and limit.")
    allocations = Field(
        List(NonNull(NumberPoolAllocation)),
        required=True,
        description="The page, ordered by value, then branch, then holder id.",
    )

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        pool_id: str,
        division: list[dict[str, str]] | None = None,
        range_id: str | None = None,
        branch: str | None = None,
        provenance: PoolRecordProvenance | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> MockAllocations:
        graphql_context: GraphqlContext = info.context
        return get_allocations(
            pool_id=pool_id,
            request_branch=graphql_context.branch.name,
            division=_division_filter(division),
            range_id=range_id,
            branch=branch,
            provenance=provenance,
            offset=offset,
            limit=limit,
        )


InfrahubNumberPoolUtilization = Field(
    NumberPoolUtilization,
    pool_id=String(required=True),
    division=List(NonNull(NumberPoolDivisionEntryInput), required=False),
    resolver=NumberPoolUtilization.resolve,
    required=True,
    description=(
        "Utilization of one number pool and of its ranges. On a scoped pool, division is required and "
        "the figures are those of that division."
    ),
)

InfrahubNumberPoolDivisions = Field(
    NumberPoolDivisions,
    pool_id=String(required=True),
    resolver=NumberPoolDivisions.resolve,
    required=True,
    description=(
        "The divisions of one number pool that hold at least one value, with their figures over the whole "
        "pool. Complete list, no pagination."
    ),
)

InfrahubNumberPoolAllocations = Field(
    NumberPoolAllocations,
    pool_id=String(required=True),
    division=List(NonNull(NumberPoolDivisionEntryInput), required=False),
    range_id=String(required=False),
    branch=String(required=False),
    provenance=PoolRecordProvenanceType(required=False),
    offset=Int(required=False),
    limit=Int(required=False),
    resolver=NumberPoolAllocations.resolve,
    required=True,
    description="The numbers one number pool tracks, filtered and paginated.",
)
