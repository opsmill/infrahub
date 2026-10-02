import asyncio

import pytest

from infrahub import lock
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.lock_utils import RESOURCE_POOL_LOCK_NAMESPACE
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.mutations.resource_manager.number_pools.pool import (
    BOUNDS_NOT_CLEARABLE,
    BOUNDS_REQUIRED,
    SHORTHAND_WITH_RANGES,
)
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_shorthand import NumberPoolShorthandMirror
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

from .helpers import BoundsCase, create_pool, execute, range_bounds, range_details, shorthand

CLEARED_BOUND_CASES = [
    BoundsCase(name="start_null", bounds="start_range: {value: null}"),
    BoundsCase(name="end_null", bounds="end_range: {value: null}"),
]


RENAME_NUMBER_POOL = """
mutation RenameNumberPool($id: String!, $name: String!) {
  CoreNumberPoolUpdate(data: {id: $id, name: {value: $name}}) {
    ok
    object { name { value } }
  }
}
"""


UPDATE_NUMBER_POOL_BOUND = """
mutation UpdateNumberPool($id: String!) {
  CoreNumberPoolUpdate(data: {id: $id, %s}) {
    ok
    object { ranges { edges { node { start { value } end { value } } } } }
  }
}
"""


UPDATE_NUMBER_POOL_START = """
mutation UpdateNumberPool($id: String!) {
  CoreNumberPoolUpdate(data: {id: $id, %s}) {
    ok
    object { start_range { value } end_range { value } }
  }
}
"""


class TestNumberPoolUpdate:
    """Bounds validation on pool update.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def ticket_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        default_branch_scope_class.update_schema_hash()

    async def test_update_untouched_bounds_are_not_validated(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        """An update that leaves the bounds alone succeeds whatever the pool holds in them."""
        pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(db=db, name="bound-less", node="TestingTicket", node_attribute="ticket_id")
        await pool.save(db=db)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=RENAME_NUMBER_POOL,
            variables={"id": pool.get_id(), "name": "bound-less-renamed"},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolUpdate"]["object"]["name"]["value"] == "bound-less-renamed"
        assert await shorthand(db=db, pool_id=pool.get_id()) == (None, None)

    @pytest.mark.parametrize("case", CLEARED_BOUND_CASES, ids=lambda case: case.name)
    async def test_update_rejects_clearing_a_bound(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None, case: BoundsCase
    ) -> None:
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name=f"clearing-pool-{case.name}",
            bounds="start_range: {value: 10}, end_range: {value: 20}",
        )

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND % case.bounds,
            variables={"id": pool_id},
        )

        assert [error.message for error in result.errors or []] == [BOUNDS_NOT_CLEARABLE]
        assert await shorthand(db=db, pool_id=pool_id) == (10, 20)
        assert await range_bounds(db=db, pool_id=pool_id) == [(10, 20)]

    async def test_bounds_written_on_a_pool_with_one_range_rewrite_it_in_place(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="rewrite-pool",
            bounds="start_range: {value: 10}, end_range: {value: 20}",
        )
        (pool_range,) = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
        pool_range.allocation_weight.value = 7
        await pool_range.save(db=db)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND % "start_range: {value: 15}, end_range: {value: 30}",
            variables={"id": pool_id},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolUpdate"]["object"]["ranges"]["edges"] == [
            {"node": {"start": {"value": 15}, "end": {"value": 30}}}
        ]
        assert await shorthand(db=db, pool_id=pool_id) == (15, 30)
        assert await range_details(db=db, pool_id=pool_id) == [(pool_range.get_id(), 15, 30, 7)]

    async def test_one_bound_written_on_a_pool_with_one_range_keeps_the_other(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="one-bound-pool",
            bounds="start_range: {value: 10}, end_range: {value: 20}",
        )
        (pool_range,) = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND % "end_range: {value: 25}",
            variables={"id": pool_id},
        )

        assert not result.errors
        assert await shorthand(db=db, pool_id=pool_id) == (10, 25)
        assert await range_details(db=db, pool_id=pool_id) == [(pool_range.get_id(), 10, 25, None)]

    async def test_bounds_written_on_a_pool_without_range_create_it(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(db=db, branch=default_branch_scope_class, name="grown-pool", bounds="")

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND % "start_range: {value: 5}, end_range: {value: 9}",
            variables={"id": pool_id},
        )

        assert not result.errors
        assert await shorthand(db=db, pool_id=pool_id) == (5, 9)
        assert await range_bounds(db=db, pool_id=pool_id) == [(5, 9)]

    async def test_one_bound_written_on_a_pool_without_range_is_refused(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(db=db, branch=default_branch_scope_class, name="half-bound-pool", bounds="")

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND % "start_range: {value: 5}",
            variables={"id": pool_id},
        )

        assert [error.message for error in result.errors or []] == [BOUNDS_REQUIRED]
        assert await shorthand(db=db, pool_id=pool_id) == (None, None)
        assert await range_bounds(db=db, pool_id=pool_id) == []

    async def test_bounds_written_on_a_pool_with_several_ranges_are_refused_listing_them(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(db=db, branch=default_branch_scope_class, name="multi-range-pool", bounds="")
        pool = await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool_id, kind=CoreNumberPool)
        high = await add_pool_range(db=db, pool=pool, start=205, end=300)
        low = await add_pool_range(db=db, pool=pool, start=100, end=200)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND % "start_range: {value: 1}, end_range: {value: 50}",
            variables={"id": pool_id},
        )

        assert [error.message for error in result.errors or []] == [
            "start_range/end_range apply to a pool holding at most one range; this pool holds: "
            f"100-200 ({low.get_id()}), 205-300 ({high.get_id()}). Edit the ranges instead."
        ]
        assert await shorthand(db=db, pool_id=pool_id) == (None, None)
        assert await range_bounds(db=db, pool_id=pool_id) == [(100, 200), (205, 300)]

    async def test_update_refuses_bounds_combined_with_ranges(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="both-spellings-update-pool",
            bounds="start_range: {value: 10}, end_range: {value: 20}",
        )
        (pool_range,) = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND
            % ('start_range: {value: 1}, end_range: {value: 50}, ranges: [{id: "%s"}]' % pool_range.get_id()),
            variables={"id": pool_id},
        )

        assert [error.message for error in result.errors or []] == [SHORTHAND_WITH_RANGES]
        assert await shorthand(db=db, pool_id=pool_id) == (10, 20)
        assert await range_bounds(db=db, pool_id=pool_id) == [(10, 20)]

    async def test_update_with_ranges_alone_is_accepted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="ranges-only-update-pool",
            bounds="start_range: {value: 10}, end_range: {value: 20}",
        )
        (pool_range,) = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_NUMBER_POOL_BOUND % ('ranges: [{id: "%s"}]' % pool_range.get_id()),
            variables={"id": pool_id},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolUpdate"]["ok"]
        assert await shorthand(db=db, pool_id=pool_id) == (10, 20)
        assert await range_details(db=db, pool_id=pool_id) == [(pool_range.get_id(), 10, 20, None)]

    async def test_one_bound_written_while_the_range_changes_keeps_its_new_other_bound(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="racing-bound-pool",
            bounds="start_range: {value: 10}, end_range: {value: 20}",
        )
        repository = NumberPoolRepository(db=db)
        (pool_range,) = await repository.get_ranges(pool_id=pool_id)
        pool_lock = lock.registry.get(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE)

        update = asyncio.create_task(
            execute(
                db=db,
                branch=default_branch_scope_class,
                source=UPDATE_NUMBER_POOL_START % "start_range: {value: 5}",
                variables={"id": pool_id},
            )
        )
        async with pool_lock, asyncio.timeout(30):
            while not pool_lock.local._waiters:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
            await repository.save_range_bounds(pool_range=pool_range, start=12, end=22)
            pool = await NodeManager.get_one_by_id_or_default_filter(db=db, id=pool_id, kind=CoreNumberPool)
            await NumberPoolShorthandMirror(repository=repository).sync(pool=pool)
        result = await update

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolUpdate"]["object"]["start_range"] == {"value": 5}
        assert result.data["CoreNumberPoolUpdate"]["object"]["end_range"] == {"value": 22}
        assert await shorthand(db=db, pool_id=pool_id) == (5, 22)
        assert await range_details(db=db, pool_id=pool_id) == [(pool_range.get_id(), 5, 22, None)]
