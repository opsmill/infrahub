from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

from .helpers import (
    CREATE_RANGE,
    DELETE_RANGE,
    UPDATE_POOL_RANGES,
    UPDATE_POOL_SHORTHAND,
    UPDATE_RANGE,
    execute,
    range_bounds,
)


@dataclass
class PoolInUse:
    """A user pool holding the ranges 100-110 and 200-210, with a ticket holding 200 on the default branch."""

    pool: CoreNumberPool
    low_range: Node
    high_range: Node
    ticket: Node


@dataclass
class RangeWriteCase:
    name: str
    source: str
    variables: dict[str, Any]


def _held_message(holders: list[tuple[Node, int, str]]) -> str:
    held = "; ".join(
        f"{TICKET.kind} {ticket.get_id()} holds {value} on branch {branch}" for ticket, value, branch in holders
    )
    return (
        f"The ranges of the pool would leave {len(holders)} number(s) it tracks outside every range: {held}. "
        "Keep ranges covering these numbers, or change the numbers first."
    )


async def _allocate_ticket(
    db: InfrahubDatabase, pool: CoreNumberPool, title: str, branch: Branch | None = None
) -> Node:
    ticket = await Node.init(db=db, schema=TICKET.kind, branch=branch)
    await ticket.new(db=db, title=title, ticket_id={"from_pool": {"id": pool.get_id()}})
    await ticket.save(db=db)
    return ticket


@pytest.fixture
async def pool_in_use(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> PoolInUse:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name="held-pool", node=TICKET.kind, node_attribute="ticket_id")
    await pool.save(db=db)
    low_range = await add_pool_range(db=db, pool=pool, start=100, end=110)
    high_range = await add_pool_range(db=db, pool=pool, start=200, end=210, weight=10)
    ticket = await _allocate_ticket(db=db, pool=pool, title="held")
    assert ticket.get_attribute("ticket_id").value == 200
    return PoolInUse(pool=pool, low_range=low_range, high_range=high_range, ticket=ticket)


def _refused_writes(pool_in_use: PoolInUse) -> list[RangeWriteCase]:
    pool_id = pool_in_use.pool.get_id()
    return [
        RangeWriteCase(
            name="range_shrunk",
            source=UPDATE_RANGE,
            variables={"range_id": pool_in_use.high_range.get_id(), "start": 201, "end": 210},
        ),
        RangeWriteCase(
            name="range_deleted", source=DELETE_RANGE, variables={"range_id": pool_in_use.high_range.get_id()}
        ),
        RangeWriteCase(
            name="pool_ranges_replaced",
            source=UPDATE_POOL_RANGES,
            variables={"pool_id": pool_id, "ranges": [{"start": 100, "end": 110}, {"start": 201, "end": 210}]},
        ),
        RangeWriteCase(
            name="pool_ranges_emptied", source=UPDATE_POOL_RANGES, variables={"pool_id": pool_id, "ranges": []}
        ),
    ]


@pytest.mark.parametrize("case_name", ["range_shrunk", "range_deleted", "pool_ranges_replaced", "pool_ranges_emptied"])
async def test_range_write_leaving_a_held_number_outside_every_range_is_refused(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse, case_name: str
) -> None:
    (case,) = [case for case in _refused_writes(pool_in_use) if case.name == case_name]

    result = await execute(db=db, branch=default_branch, source=case.source, variables=case.variables)

    assert result.errors
    assert result.errors[0].message == _held_message([(pool_in_use.ticket, 200, default_branch.name)])
    assert await range_bounds(db=db, pool_id=pool_in_use.pool.get_id()) == [(100, 110), (200, 210)]


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
    assert result.errors[0].message == _held_message([(tickets[0], 1, default_branch.name)])
    assert await range_bounds(db=db, pool_id=pool.get_id()) == [(1, 10)]


async def test_refusal_names_each_branch_holding_a_number_outside_the_ranges(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    branch = await create_branch(branch_name="branch-held", db=db)
    branch_ticket = await _allocate_ticket(db=db, pool=pool_in_use.pool, title="on-branch", branch=branch)
    assert branch_ticket.get_attribute("ticket_id").value == 201
    ticket_on_branch = await NodeManager.get_one(
        db=db, id=pool_in_use.ticket.get_id(), branch=branch, raise_on_error=True
    )
    ticket_on_branch.get_attribute("ticket_id").value = 203
    await ticket_on_branch.save(db=db)

    result = await execute(
        db=db,
        branch=default_branch,
        source=UPDATE_RANGE,
        variables={"range_id": pool_in_use.high_range.get_id(), "start": 204, "end": 210},
    )

    assert result.errors
    assert result.errors[0].message == _held_message(
        [
            (pool_in_use.ticket, 200, default_branch.name),
            (branch_ticket, 201, branch.name),
            (pool_in_use.ticket, 203, branch.name),
        ]
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


async def test_number_already_outside_the_ranges_is_refused_until_a_range_covers_it(
    db: InfrahubDatabase, default_branch: Branch, pool_in_use: PoolInUse
) -> None:
    """The range holding 200 is deleted directly, which the mutations refuse to do."""
    await pool_in_use.high_range.delete(db=db)
    pool_id = pool_in_use.pool.get_id()

    not_covering = await execute(
        db=db,
        branch=default_branch,
        source=CREATE_RANGE,
        variables={"pool_id": pool_id, "start": 300, "end": 310, "weight": None},
    )
    covering = await execute(
        db=db,
        branch=default_branch,
        source=CREATE_RANGE,
        variables={"pool_id": pool_id, "start": 200, "end": 210, "weight": None},
    )

    assert not_covering.errors
    assert not_covering.errors[0].message == _held_message([(pool_in_use.ticket, 200, default_branch.name)])
    assert not covering.errors
    assert await range_bounds(db=db, pool_id=pool_id) == [(100, 110), (200, 210)]
