from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import BigInt, Boolean, Enum, Field, Float, InputObjectType, Int, List, NonNull, ObjectType, String

from infrahub.core.query.resource_manager import PoolRecordProvenance
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

    from infrahub.graphql.initialization import GraphqlContext


NumberPoolProvenance = Enum.from_enum(
    PoolRecordProvenance,
    name="NumberPoolProvenance",
    description="How the number a tracked attribute currently holds got there.",
)


class NumberPoolUtilizationFigures(ObjectType):
    class Meta:
        description = "Absolute and relative utilization of one space: a pool, a range or a division."

    size = Field(
        BigInt, required=True, description="Number of values the measured space holds. 0 when the pool has no range."
    )
    used = Field(BigInt, required=True, description="Distinct values of the space held on any live branch.")
    used_default_branch = Field(
        BigInt, required=True, description="Distinct values of the space held on the default branch."
    )
    used_branches = Field(
        BigInt,
        required=True,
        description="Distinct values of the space held on other branches and not on the default branch.",
    )
    utilization = Field(Float, required=True, description="used as a percentage of size. 0 when size is 0.")
    utilization_default_branch = Field(
        Float, required=True, description="used_default_branch as a percentage of size. 0 when size is 0."
    )
    utilization_branches = Field(
        Float, required=True, description="used_branches as a percentage of size. 0 when size is 0."
    )


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
            "Figures over the range's values. On a scoped pool, the figures of the division holding the most\n"
            "of this range's values."
        ),
    )


class NumberPoolUtilization(ObjectType):
    class Meta:
        description = (
            "Utilization of one number pool and of each of its ranges, with the allocation scope in force on\n"
            "the request's branch. For a number pool, prefer this over InfrahubResourcePoolUtilization."
        )

    id = Field(String, required=True, description="The pool's id, as given in pool_id.")
    display_label = Field(String, required=True, description="The pool's display label, read on the request's branch.")
    allocation_scope = Field(
        List(NonNull(String)),
        required=True,
        description=(
            "Scope entries in force on the request's branch, in scope order. Empty for an unscoped pool,\n"
            "and for a scoped pool none of whose entries the branch's schema defines."
        ),
    )
    figures = Field(
        NumberPoolUtilizationFigures,
        required=True,
        description="Figures over the pool's whole space. On a scoped pool, the figures of the fullest division.",
    )
    ranges = Field(
        List(NonNull(NumberPoolRangeUtilization)),
        required=True,
        description="The pool's ranges ordered by start, each with its own figures.",
    )
    out_of_space_count = Field(
        BigInt,
        required=True,
        description="Number of allocation rows whose value lies outside the pool's space (in_space false).",
    )

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,  # noqa: ARG004
        pool_id: str,
    ) -> MockUtilization:
        return get_utilization(pool_id=pool_id)


class NumberPoolDivisionEntry(ObjectType):
    class Meta:
        description = "The value one scope entry takes in a division."

    path = Field(String, required=True, description='The scope entry, as stored on the pool ("site", "role").')
    value = Field(
        String,
        required=True,
        description=(
            "Relationship entry: the peer's id. Attribute entry: the value as text. A holder holding nothing\n"
            "for the entry: an empty string."
        ),
    )
    display_label = Field(
        String,
        required=True,
        description=(
            "Relationship entry: the peer's display label, read on any branch, falling back to the peer's id\n"
            "when the peer cannot be read. Attribute entry: the value as text."
        ),
    )
    peer_kind = Field(
        String,
        required=False,
        description="Relationship entry: the peer's kind when the peer can be read. Otherwise null.",
    )


class NumberPoolDivisionEntryInput(InputObjectType):
    class Meta:
        description = "One entry of a division filter. Mirrors NumberPoolDivisionEntry."

    path = String(required=True, description="A scope entry in force on the request's branch.")
    value = String(required=True, description="Relationship entry: the peer's id. Attribute entry: the value as text.")


class NumberPoolDivision(ObjectType):
    class Meta:
        description = "One division: a tuple of values of the scope in force."

    display_label = Field(
        String,
        required=True,
        description='The entries\' display labels joined with " / ". Empty for the division of an unscoped pool.',
    )
    entries = Field(
        List(NonNull(NumberPoolDivisionEntry)),
        required=True,
        description="One entry per scope entry in force, in scope order.",
    )
    figures = Field(
        NumberPoolUtilizationFigures,
        required=True,
        description="Figures over the pool's space, or over the range given as range_id, for this division.",
    )


class NumberPoolDivisions(ObjectType):
    class Meta:
        description = "The divisions of one number pool, each with its figures."

    count = Field(Int, required=True, description="Number of divisions listed.")
    allocation_scope = Field(
        List(NonNull(String)),
        required=True,
        description="Scope entries in force on the request's branch, in scope order.",
    )
    divisions = Field(
        List(NonNull(NumberPoolDivision)),
        required=True,
        description=(
            "Every division occupied by a node of the pool's kind on any live branch, ordered by utilization\n"
            "descending then by display_label. An unscoped pool lists one division with no entry."
        ),
    )

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,  # noqa: ARG004
        pool_id: str,
        range_id: str | None = None,
    ) -> MockDivisions:
        return get_divisions(pool_id=pool_id, range_id=range_id)


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
        NumberPoolProvenance,
        required=True,
        description="ALLOCATED when the pool picked the number, PROVIDED when a user gave it.",
    )
    in_space = Field(
        Boolean,
        required=True,
        description=(
            "Whether the value lies inside the pool's space and counts in its figures: inside a range, not\n"
            "excluded by the attribute, within its min and max. False for an excluded or out-of-limits value\n"
            "even when a range holds it."
        ),
    )
    range = Field(NumberPoolRangeRef, description="The range whose bounds hold the value. Null when no range holds it.")
    division = Field(
        List(NonNull(NumberPoolDivisionEntry)),
        required=True,
        description="The holder's division on the row's branch, in scope order. Empty when the pool is unscoped.",
    )


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
        division: list[dict[str, Any]] | None = None,
        range_id: str | None = None,
        in_space: bool | None = None,
        branch: str | None = None,
        provenance: PoolRecordProvenance | str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> MockAllocations:
        graphql_context: GraphqlContext = info.context
        return get_allocations(
            pool_id=pool_id,
            request_branch=graphql_context.branch.name,
            division=[DivisionFilterEntry(path=entry["path"], value=entry["value"]) for entry in division]
            if division is not None
            else None,
            range_id=range_id,
            in_space=in_space,
            branch=branch,
            provenance=PoolRecordProvenance(provenance) if provenance is not None else None,
            offset=offset,
            limit=limit,
        )


InfrahubNumberPoolUtilization = Field(
    NumberPoolUtilization,
    pool_id=String(required=True),
    resolver=NumberPoolUtilization.resolve,
    required=True,
    description="Utilization of one number pool and of its ranges.",
)

InfrahubNumberPoolDivisions = Field(
    NumberPoolDivisions,
    pool_id=String(required=True),
    range_id=String(required=False),
    resolver=NumberPoolDivisions.resolve,
    required=True,
    description=(
        "The divisions of one number pool with their figures, over the whole pool or over one range.\n"
        "Complete list, no pagination."
    ),
)

InfrahubNumberPoolAllocations = Field(
    NumberPoolAllocations,
    pool_id=String(required=True),
    division=List(NonNull(NumberPoolDivisionEntryInput), required=False),
    range_id=String(required=False),
    in_space=Boolean(required=False),
    branch=String(required=False),
    provenance=NumberPoolProvenance(required=False),
    offset=Int(required=False),
    limit=Int(required=False),
    resolver=NumberPoolAllocations.resolve,
    required=True,
    description="The numbers one number pool tracks, filtered and paginated.",
)
