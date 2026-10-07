from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.database import InfrahubDatabase
from tests.helpers.agnostic_edges import attribute_edges

from .helpers import (
    allocated_rows,
    create_ticket,
    is_reserved_edges,
    new_pool,
    open_is_reserved_edges,
    update_ticket,
)

REMOVE_ALLOCATED_VALUES = """
MATCH (:Node { uuid: $pool_id })-[reserved:IS_RESERVED]->(:Attribute)
WHERE reserved.status = "active" AND reserved.to IS NULL
REMOVE reserved.allocated_values
"""


async def _rows_on(
    db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool, branch_name: str
) -> list[tuple[int, str]]:
    """The value and provenance of the pool's in-use rows held by one branch."""
    rows = await allocated_rows(db=db, branch=branch, pool=pool)
    return [(value, provenance) for _, row_branch, value, provenance in rows if row_branch == branch_name]


class TestProvenanceAcrossBranches:
    """Whether the pool allocated a number or a user provided it is read per branch, from the number that branch holds.

    Every test allocates on the default branch and provides on a branch, or the reverse, over its own pool and
    number range, so the rows of one test never meet another's.
    """

    @pytest.mark.parametrize("allocate_first", [True, False], ids=["allocate_then_provide", "provide_then_allocate"])
    async def test_each_branch_reads_the_provenance_of_the_number_it_holds(
        self, db: InfrahubDatabase, main_branch: Branch, allocate_first: bool
    ) -> None:
        start = 2000 if allocate_first else 2100
        pool = await new_pool(
            db=db, name=f"per-branch-{start}", start_range=start, end_range=start + 9, node_attribute="sequence"
        )
        ticket = await create_ticket(
            db=db, branch=main_branch, title=f"per-branch-{start}", ticket_id={"value": start + 90}
        )
        allocating = await create_branch(branch_name=f"per-branch-{start}-allocating", db=db)
        providing = await create_branch(branch_name=f"per-branch-{start}-providing", db=db)

        async def allocate() -> None:
            # Sent with `value: null`, so the write allocates whether or not the pool already tracks the attribute.
            changed = await update_ticket(
                db=db, branch=allocating, node_id=ticket["id"], sequence={"value": None, "from_pool": {"id": pool.id}}
            )
            assert changed["sequence"]["value"] == start

        async def provide() -> None:
            await update_ticket(
                db=db,
                branch=providing,
                node_id=ticket["id"],
                sequence={"value": start + 5, "from_pool": {"id": pool.id}},
            )

        for step in (allocate, provide) if allocate_first else (provide, allocate):
            await step()

        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [
            (ticket["id"], allocating.name, start, "allocated"),
            (ticket["id"], providing.name, start + 5, "provided"),
        ]
        assert await open_is_reserved_edges(db=db, pool=pool) == {(ticket["id"], (start,))}, (
            "one record serves both branches"
        )

    async def test_a_pool_tracking_the_current_number_lists_it_as_provided_until_it_allocates_another(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """Naming another pool with the number in hand makes it a provided number, and a later allocation from that pool extends its record."""
        first_pool = await new_pool(db=db, name="re-pool-first", start_range=2200, end_range=2209)
        second_pool = await new_pool(db=db, name="re-pool-second", start_range=2200, end_range=2219)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="re-pool-current", ticket_id={"from_pool": {"id": first_pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 2200
        branch = await create_branch(branch_name="re-pool-current", db=db)

        await update_ticket(
            db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": 2200, "from_pool": {"id": second_pool.id}}
        )

        assert await open_is_reserved_edges(db=db, pool=first_pool) == set()
        assert await open_is_reserved_edges(db=db, pool=second_pool) == {(ticket["id"], ())}
        assert await allocated_rows(db=db, branch=main_branch, pool=second_pool) == [
            (ticket["id"], "main", 2200, "provided")
        ], "the number the first pool allocated is one the second pool only tracks"
        records = await is_reserved_edges(db=db, node_id=ticket["id"])
        assert sorted((record.status, record.is_open) for record in records) == [("active", False), ("active", True)]

        # The tracking pool returns a number the branch still holds, so the branch clears it before allocating.
        other = await create_branch(branch_name="re-pool-current-other", db=db)
        await update_ticket(db=db, branch=other, node_id=ticket["id"], ticket_id={"value": None})
        changed = await update_ticket(
            db=db, branch=other, node_id=ticket["id"], ticket_id={"value": None, "from_pool": {"id": second_pool.id}}
        )

        assert changed["ticket_id"]["value"] == 2201
        assert await open_is_reserved_edges(db=db, pool=second_pool) == {(ticket["id"], (2201,))}
        records = await is_reserved_edges(db=db, node_id=ticket["id"])
        assert sorted((record.status, record.is_open) for record in records) == [
            ("active", False),
            ("active", False),
            ("active", True),
        ], "extending the list closes the record and creates another"
        assert await allocated_rows(db=db, branch=main_branch, pool=second_pool) == sorted(
            [(ticket["id"], "main", 2200, "provided"), (ticket["id"], other.name, 2201, "allocated")]
        )

    async def test_restating_an_inherited_allocation_on_a_branch_keeps_it_allocated(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="restate-branch", start_range=2300, end_range=2309)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="restate-branch", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 2300
        branch = await create_branch(branch_name="restate-branch", db=db)
        before = await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id")

        await update_ticket(
            db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": 2300, "from_pool": {"id": pool.id}}
        )

        assert await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id") == before
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [(ticket["id"], "main", 2300, "allocated")]

    async def test_a_number_set_back_by_hand_to_the_one_the_pool_allocated_reads_as_allocated(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """The label is read from the number alone, so a branch cannot tell its own hand-set copy from the allocation."""
        pool = await new_pool(db=db, name="set-back", start_range=2400, end_range=2409)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="set-back", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 2400
        branch = await create_branch(branch_name="set-back", db=db)

        await update_ticket(db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": 2409})
        assert await _rows_on(db=db, branch=main_branch, pool=pool, branch_name=branch.name) == [(2409, "provided")]

        await update_ticket(db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": 2400})

        assert await _rows_on(db=db, branch=main_branch, pool=pool, branch_name=branch.name) == [(2400, "allocated")]
        assert await _rows_on(db=db, branch=main_branch, pool=pool, branch_name="main") == [(2400, "allocated")]

    async def test_discarding_a_provided_number_in_favour_of_its_tracking_pool_keeps_the_number(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """The tracking pool returns the number it already holds for the object, so nothing is written and the label stays."""
        pool = await new_pool(db=db, name="discard-held", start_range=2500, end_range=2509)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="discard-held", ticket_id={"value": 2505, "from_pool": {"id": pool.id}}
        )
        before = await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id")

        changed = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": None, "from_pool": {"id": pool.id}}
        )

        assert changed["ticket_id"]["value"] == 2505
        assert await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id") == before
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [(ticket["id"], "main", 2505, "provided")]

    async def _allocated_on_main_and_provided_on_a_branch(
        self, db: InfrahubDatabase, main_branch: Branch, name: str, start: int
    ) -> tuple[CoreNumberPool, dict[str, Any], Branch]:
        pool = await new_pool(db=db, name=name, start_range=start, end_range=start + 9)
        ticket = await create_ticket(db=db, branch=main_branch, title=name, ticket_id={"from_pool": {"id": pool.id}})
        assert ticket["ticket_id"]["value"] == start
        branch = await create_branch(branch_name=name, db=db)
        await update_ticket(
            db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": start + 4, "from_pool": {"id": pool.id}}
        )
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == sorted(
            [(ticket["id"], branch.name, start + 4, "provided"), (ticket["id"], "main", start, "allocated")]
        )
        return pool, ticket, branch

    async def test_a_record_without_a_list_reads_as_allocated_on_every_branch(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """A record written before the list existed accounts for whatever number each branch holds as an allocation."""
        pool, ticket, branch = await self._allocated_on_main_and_provided_on_a_branch(
            db=db, main_branch=main_branch, name="no-list", start=3000
        )

        await db.execute_query(query=REMOVE_ALLOCATED_VALUES, params={"pool_id": pool.get_id()})

        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == sorted(
            [(ticket["id"], branch.name, 3004, "allocated"), (ticket["id"], "main", 3000, "allocated")]
        )
