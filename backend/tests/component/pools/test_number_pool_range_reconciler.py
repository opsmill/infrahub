import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolRangeParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_range_reconciler import NumberPoolRangeReconciler
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema


async def _pool(db: InfrahubDatabase, name: str) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node=TICKET.kind, node_attribute="ticket_id")
    await pool.save(db=db)
    return pool


async def _ranges(db: InfrahubDatabase, pool: CoreNumberPool) -> list[tuple[str, int, int, int | None]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
    return [(item.get_id(), item.start.value, item.end.value, item.allocation_weight.value) for item in ranges]


class TestNumberPoolRangeReconciler:
    """Reconciliations written through the repository to the real database.

    The schema is loaded once for the class; every test works on a pool of its own.
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

    async def test_reconcile_writes_the_ranges_through_the_repository(
        self, db: InfrahubDatabase, ticket_schema: None
    ) -> None:
        pool = await _pool(db=db, name="reconcile-round-trip")
        kept = await add_pool_range(db=db, pool=pool, start=1, end=10)
        removed = await add_pool_range(db=db, pool=pool, start=20, end=30)
        reweighted = await add_pool_range(db=db, pool=pool, start=40, end=50)

        reconciliation = await NumberPoolRangeReconciler(range_store=NumberPoolRepository(db=db)).reconcile(
            pool=pool,
            declared=[
                NumberPoolRangeParameters(start=1, end=10),
                NumberPoolRangeParameters(start=40, end=50, weight=3),
                NumberPoolRangeParameters(start=60, end=70),
            ],
        )

        (created,) = reconciliation.created
        assert [item.get_id() for item in reconciliation.updated] == [reweighted.get_id()]
        assert [item.get_id() for item in reconciliation.deleted] == [removed.get_id()]
        stored = await _ranges(db=db, pool=pool)
        assert stored == [
            (kept.get_id(), 1, 10, None),
            (reweighted.get_id(), 40, 50, 3),
            (created.get_id(), 60, 70, None),
        ]
        assert [item.get_id() for item in reconciliation.ranges] == [item[0] for item in stored]

    async def test_single_range_rewrite_keeps_the_identity_of_the_stored_range(
        self, db: InfrahubDatabase, ticket_schema: None
    ) -> None:
        pool = await _pool(db=db, name="rewrite-round-trip")
        stored = await add_pool_range(db=db, pool=pool, start=1, end=10, weight=2)

        reconciliation = await NumberPoolRangeReconciler(range_store=NumberPoolRepository(db=db)).rewrite_single_range(
            pool=pool, declared=NumberPoolRangeParameters(start=50, end=60, weight=2)
        )

        assert [item.get_id() for item in reconciliation.updated] == [stored.get_id()]
        assert await _ranges(db=db, pool=pool) == [(stored.get_id(), 50, 60, 2)]
