from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations.resource_manager.number_pools import common
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    add_pool_range,
    save_schema_kinds,
    scoped_device,
    scoped_pool,
    scoped_site,
)
from tests.helpers.schema import TICKET, load_schema

from .helpers import (
    CREATE_RANGE,
    DELETE_RANGE,
    UPDATE_POOL_RANGES,
    UPDATE_POOL_SHORTHAND,
    UPDATE_RANGE,
    UPSERT_RANGE,
    execute,
    range_bounds,
)

POOL_NAME = "held-pool"


@dataclass
class PoolInUse:
    """A user pool holding the ranges 100-110 and 200-210, with a ticket holding 200 on the default branch."""

    pool: CoreNumberPool
    low_range: Node
    high_range: Node
    ticket: Node


@dataclass
class Held:
    label: str
    value: int
    branches: list[str]
    kind: str = TICKET.kind


@dataclass
class RangeWriteCase:
    name: str
    source: str
    variables: dict[str, Any]
    ranges: str


def _held_message(ranges: str, held: list[Held], more: int = 0, pool_name: str = POOL_NAME) -> str:
    listed = "; ".join(
        f"{item.kind} '{item.label}' holds {item.value} on "
        f"{'branch' if len(item.branches) == 1 else 'branches'} {', '.join(repr(branch) for branch in item.branches)}"
        for item in held
    )
    if more:
        listed += f"; and {more} more"
    return (
        f"Changing the ranges of the {pool_name} pool to {ranges} would leave numbers it tracks outside every range: "
        f"{listed}. Keep a range covering each of these numbers, or change those numbers first."
    )


async def _label(db: InfrahubDatabase, node: Node) -> str:
    return await node.get_display_label(db=db)


async def _allocate_ticket(
    db: InfrahubDatabase, pool: CoreNumberPool, title: str, branch: Branch | None = None
) -> Node:
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=branch)
    await ticket.new(db=db, title=title, ticket_id={"from_pool": {"id": pool.get_id()}})
    await ticket.save(db=db)
    return ticket


async def _set_ticket_id(db: InfrahubDatabase, ticket: Node, branch: Branch, value: int) -> None:
    ticket_on_branch = await NodeManager.get_one(db=db, id=ticket.get_id(), branch=branch, raise_on_error=True)
    ticket_on_branch.get_attribute("ticket_id").value = value
    await ticket_on_branch.save(db=db)


@pytest.fixture
async def pool_in_use(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> PoolInUse:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=POOL_NAME, node=TICKET.kind, node_attribute="ticket_id")
    await pool.save(db=db)
    low_range = await add_pool_range(db=db, pool=pool, start=100, end=110)
    high_range = await add_pool_range(db=db, pool=pool, start=200, end=210, weight=10)
    ticket = await _allocate_ticket(db=db, pool=pool, title="held")
    assert ticket.get_attribute("ticket_id").value == 200
    return PoolInUse(pool=pool, low_range=low_range, high_range=high_range, ticket=ticket)


def _refused_writes(pool_in_use: PoolInUse) -> list[RangeWriteCase]:
    pool_id = pool_in_use.pool.get_id()
    high_range_id = pool_in_use.high_range.get_id()
    return [
        RangeWriteCase(
            name="range_narrowed",
            source=UPDATE_RANGE,
            variables={"range_id": high_range_id, "start": 201, "end": 210},
            ranges="100-110, 201-210",
        ),
        RangeWriteCase(
            name="range_upserted_narrower",
            source=UPSERT_RANGE,
            variables={"range_id": high_range_id, "pool_id": pool_id, "start": 201, "end": 210},
            ranges="100-110, 201-210",
        ),
        RangeWriteCase(
            name="range_deleted", source=DELETE_RANGE, variables={"range_id": high_range_id}, ranges="100-110"
        ),
        RangeWriteCase(
            name="pool_ranges_replaced",
            source=UPDATE_POOL_RANGES,
            variables={"pool_id": pool_id, "ranges": [{"start": 100, "end": 110}, {"start": 201, "end": 210}]},
            ranges="100-110, 201-210",
        ),
        RangeWriteCase(
            name="pool_ranges_emptied",
            source=UPDATE_POOL_RANGES,
            variables={"pool_id": pool_id, "ranges": []},
            ranges="no ranges",
        ),
    ]


async def test_range_write_leaving_a_held_number_outside_every_range_is_refused(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    """Each refused write rolls back, so every case runs against the same pool."""
    cases = _refused_writes(pool_in_use)
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    outcomes: dict[str, tuple[str | None, list[tuple[int, int]]]] = {}

    for case in cases:
        result = await graphql(
            schema=gql_params.schema,
            source=case.source,
            context_value=gql_params.context,
            root_value=None,
            variable_values=case.variables,
        )
        outcomes[case.name] = (
            result.errors[0].message if result.errors else None,
            await range_bounds(db=db, pool_id=pool_in_use.pool.get_id()),
        )

    assert outcomes == {
        case.name: (
            _held_message(
                ranges=case.ranges,
                held=[Held(label=await _label(db=db, node=pool_in_use.ticket), value=200, branches=["main"])],
            ),
            [(100, 110), (200, 210)],
        )
        for case in cases
    }


async def test_shorthand_update_leaving_a_held_number_outside_the_range_is_refused(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db, name="shorthand-pool", node=TICKET.kind, node_attribute="ticket_id", start_range=1, end_range=10
    )
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=10)
    tickets = [await _allocate_ticket(db=db, pool=pool, title=f"ticket-{index}") for index in range(3)]

    result = await execute(
        db=db,
        branch=default_branch,
        source=UPDATE_POOL_SHORTHAND,
        variables={"pool_id": pool.get_id(), "start": 2, "end": 10},
    )

    assert result.errors
    assert result.errors[0].message == _held_message(
        ranges="2-10",
        held=[Held(label=await _label(db=db, node=tickets[0]), value=1, branches=["main"])],
        pool_name="shorthand-pool",
    )
    assert await range_bounds(db=db, pool_id=pool.get_id()) == [(1, 10)]


async def test_refusal_lists_each_number_once_with_every_branch_holding_it(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    branch_a = await create_branch(branch_name="branch-a", db=db)
    branch_b = await create_branch(branch_name="branch-b", db=db)
    await create_branch(branch_name="branch-c", db=db)
    branch_ticket = await _allocate_ticket(db=db, pool=pool_in_use.pool, title="on-branch", branch=branch_a)
    assert branch_ticket.get_attribute("ticket_id").value == 201
    for branch in (branch_a, branch_b):
        await _set_ticket_id(db=db, ticket=pool_in_use.ticket, branch=branch, value=203)

    result = await execute(
        db=db,
        branch=default_branch,
        source=UPDATE_RANGE,
        variables={"range_id": pool_in_use.high_range.get_id(), "start": 204, "end": 210},
    )

    assert result.errors
    assert result.errors[0].message == _held_message(
        ranges="100-110, 204-210",
        held=[
            Held(label=await _label(db=db, node=pool_in_use.ticket), value=200, branches=["branch-c", "main"]),
            Held(label=await _label(db=db, node=branch_ticket), value=201, branches=["branch-a"]),
            Held(label=await _label(db=db, node=pool_in_use.ticket), value=203, branches=["branch-a", "branch-b"]),
        ],
    )


async def test_refusal_lists_the_lowest_numbers_and_counts_the_others(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(common, "HELD_OUTSIDE_RANGES_LISTED", 1)
    for index in range(2):
        await _allocate_ticket(db=db, pool=pool_in_use.pool, title=f"other-{index}")

    result = await execute(
        db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": pool_in_use.high_range.get_id()}
    )

    assert result.errors
    assert result.errors[0].message == _held_message(
        ranges="100-110",
        held=[Held(label=await _label(db=db, node=pool_in_use.ticket), value=200, branches=["main"])],
        more=2,
    )


async def test_range_write_keeping_every_held_number_inside_the_ranges_is_accepted(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    result = await execute(
        db=db,
        branch=default_branch,
        source=UPDATE_RANGE,
        variables={"range_id": pool_in_use.high_range.get_id(), "start": 200, "end": 220},
    )

    assert not result.errors
    assert await range_bounds(db=db, pool_id=pool_in_use.pool.get_id()) == [(100, 110), (200, 220)]


async def test_writes_removing_no_number_from_the_ranges_are_accepted(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    pool_id = pool_in_use.pool.get_id()

    for source, variables in (
        (CREATE_RANGE, {"pool_id": pool_id, "start": 300, "end": 310, "weight": None}),
        (UPDATE_RANGE, {"range_id": pool_in_use.high_range.get_id(), "start": 200, "end": 210}),
        (
            UPDATE_POOL_RANGES,
            {
                "pool_id": pool_id,
                "ranges": [
                    {"start": 100, "end": 110},
                    {"start": 200, "end": 210, "allocation_weight": 10},
                    {"start": 300, "end": 310},
                ],
            },
        ),
    ):
        result = await execute(db=db, branch=default_branch, source=source, variables=variables)
        assert not result.errors, source

    assert await range_bounds(db=db, pool_id=pool_id) == [(100, 110), (200, 210), (300, 310)]


async def test_write_removing_numbers_without_any_held_inside_them_is_accepted(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    result = await execute(
        db=db,
        branch=default_branch,
        source=UPDATE_RANGE,
        variables={"range_id": pool_in_use.low_range.get_id(), "start": 101, "end": 110},
    )

    assert not result.errors
    assert await range_bounds(db=db, pool_id=pool_in_use.pool.get_id()) == [(101, 110), (200, 210)]


async def test_a_number_already_outside_the_ranges_refuses_range_changes_until_one_covers_it(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    """The range holding 200 is deleted directly, which the mutations refuse to do."""
    await pool_in_use.high_range.delete(db=db)
    pool_id = pool_in_use.pool.get_id()

    for source, variables in (
        (UPDATE_POOL_RANGES, {"pool_id": pool_id, "ranges": [{"start": 100, "end": 110}]}),
        (UPDATE_RANGE, {"range_id": pool_in_use.low_range.get_id(), "start": 100, "end": 110}),
    ):
        unchanged = await execute(db=db, branch=default_branch, source=source, variables=variables)
        assert not unchanged.errors, source
    unrelated = await execute(
        db=db,
        branch=default_branch,
        source=CREATE_RANGE,
        variables={"pool_id": pool_id, "start": 300, "end": 310, "weight": None},
    )
    covering = await execute(
        db=db,
        branch=default_branch,
        source=UPDATE_POOL_RANGES,
        variables={"pool_id": pool_id, "ranges": [{"start": 100, "end": 110}, {"start": 200, "end": 210}]},
    )

    assert unrelated.errors
    assert unrelated.errors[0].message == _held_message(
        ranges="100-110, 300-310",
        held=[Held(label=await _label(db=db, node=pool_in_use.ticket), value=200, branches=["main"])],
    )
    assert not covering.errors
    assert await range_bounds(db=db, pool_id=pool_id) == [(100, 110), (200, 210)]


async def test_scoped_pool_refuses_a_range_write_leaving_a_number_of_any_division_outside(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await save_schema_kinds(db=db, schema=SCOPED_POOL_SCHEMA)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await scoped_pool(db=db, name="vlan-per-site", allocation_scope=["site"])
    devices = [
        await scoped_device(
            db=db,
            branch=default_branch,
            pool=pool,
            name=f"device-{name}",
            site=await scoped_site(db=db, branch=default_branch, name=f"site-{name}"),
        )
        for name in ("a", "b")
    ]

    result = await execute(
        db=db,
        branch=default_branch,
        source=UPDATE_POOL_RANGES,
        variables={"pool_id": pool.get_id(), "ranges": [{"start": 2, "end": 10}]},
    )

    assert result.errors
    held = sorted(devices, key=lambda device: device.get_attribute(SCOPED_ATTRIBUTE_NAME).id or "")
    assert result.errors[0].message == _held_message(
        ranges="2-10",
        held=[
            Held(label=await _label(db=db, node=device), value=1, branches=["main"], kind=SCOPED_DEVICE.kind)
            for device in held
        ],
        pool_name="vlan-per-site",
    )
    assert await range_bounds(db=db, pool_id=pool.get_id()) == [(1, 10)]
