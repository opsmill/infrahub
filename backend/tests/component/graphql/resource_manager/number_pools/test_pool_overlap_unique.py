import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import TICKET

from .helpers import (
    CREATE_NUMBER_POOL_WITH_BOUNDS,
    CREATE_RANGE,
    UPDATE_POOL_RANGES,
    UPDATE_RANGE,
    create_pool,
    execute,
    range_bounds,
    range_details,
    ticket_pool_input,
)


def overlap_refusal(pool: str, clashes: str) -> str:
    return (
        f"The '{pool}' pool cannot share numbers with another pool on the unique attribute 'ticket_id': {clashes}. "
        "Choose ranges that no other pool on 'ticket_id' uses."
    )


class TestNumberPoolOverlapOnUniqueAttribute:
    """Range writes of pools over the unique `ticket_id` against one pool already holding 10 - 20.

    Every write through `refused_writes_pool` is refused, so its range stays 30 - 40 whatever order the tests run in.
    """

    @pytest.fixture(scope="class")
    async def existing_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, loaded_ticket_schema_scope_class: None
    ) -> str:
        return await create_pool(
            db=db, branch=default_branch_scope_class, name="existing", bounds={"ranges": [{"start": 10, "end": 20}]}
        )

    @pytest.fixture(scope="class")
    async def refused_writes_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, existing_pool: str
    ) -> str:
        return await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="refused-writes",
            bounds={"ranges": [{"start": 30, "end": 40}]},
        )

    async def test_a_pool_overlapping_another_is_refused_on_a_branch_where_the_attribute_is_not_unique(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, refused_writes_pool: str
    ) -> None:
        """A pool serves every branch, so the default branch's uniqueness applies to range writes on any branch."""
        branch = await create_branch(branch_name="shared-ticket-number", db=db)
        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        ticket = schema_branch.get_node(name=TICKET.kind)
        ticket.get_attribute(name="ticket_id").unique = False
        schema_branch.set(name=TICKET.kind, schema=ticket)

        result = await execute(
            db=db,
            branch=branch,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={
                "data": ticket_pool_input(name="branch-overlapping", bounds={"ranges": [{"start": 12, "end": 14}]})
            },
        )

        assert [error.message for error in result.errors or []] == [
            overlap_refusal(pool="branch-overlapping", clashes="12 - 14 overlaps 10 - 20 of the 'existing' pool")
        ]
        assert (
            await NodeManager.query(
                db=db, schema=InfrahubKind.NUMBERPOOL, filters={"name__value": "branch-overlapping"}
            )
            == []
        )

    async def test_creating_a_pool_overlapping_another_pool_is_refused_and_creates_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, refused_writes_pool: str
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={
                "data": ticket_pool_input(
                    name="overlapping", bounds={"ranges": [{"start": 50, "end": 60}, {"start": 15, "end": 25}]}
                )
            },
        )

        assert [error.message for error in result.errors or []] == [
            overlap_refusal(pool="overlapping", clashes="15 - 25 overlaps 10 - 20 of the 'existing' pool")
        ]
        assert (
            await NodeManager.query(db=db, schema=InfrahubKind.NUMBERPOOL, filters={"name__value": "overlapping"}) == []
        )

    async def test_updating_ranges_to_overlap_another_pool_is_refused_and_keeps_the_ranges(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, refused_writes_pool: str
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_POOL_RANGES,
            variables={"pool_id": refused_writes_pool, "ranges": [{"start": 15, "end": 40}]},
        )

        assert [error.message for error in result.errors or []] == [
            overlap_refusal(pool="refused-writes", clashes="15 - 40 overlaps 10 - 20 of the 'existing' pool")
        ]
        assert await range_bounds(db=db, pool_id=refused_writes_pool) == [(30, 40)]

    async def test_adding_a_range_overlapping_another_pool_is_refused_and_adds_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, refused_writes_pool: str
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_RANGE,
            variables={"pool_id": refused_writes_pool, "start": 5, "end": 12, "weight": None},
        )

        assert [error.message for error in result.errors or []] == [
            overlap_refusal(pool="refused-writes", clashes="5 - 12 overlaps 10 - 20 of the 'existing' pool")
        ]
        assert await range_bounds(db=db, pool_id=refused_writes_pool) == [(30, 40)]

    async def test_moving_a_range_onto_another_pool_s_numbers_is_refused_and_keeps_the_range(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, refused_writes_pool: str
    ) -> None:
        [(range_id, _, _, _)] = await range_details(db=db, pool_id=refused_writes_pool)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_RANGE,
            variables={"range_id": range_id, "start": 18, "end": 38},
        )

        assert [error.message for error in result.errors or []] == [
            overlap_refusal(pool="refused-writes", clashes="18 - 38 overlaps 10 - 20 of the 'existing' pool")
        ]
        assert await range_bounds(db=db, pool_id=refused_writes_pool) == [(30, 40)]

    async def test_a_pool_next_to_another_pool_is_accepted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, refused_writes_pool: str
    ) -> None:
        pool_id = await create_pool(
            db=db, branch=default_branch_scope_class, name="adjacent", bounds={"ranges": [{"start": 41, "end": 49}]}
        )

        assert await range_bounds(db=db, pool_id=pool_id) == [(41, 49)]
