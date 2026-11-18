import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.protocols import CoreNumberPoolRange
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema


class TestNumberPoolRangeBranchReads:
    """Ranges added to a pool on main after a branch was created, read without the branch-agnostic flag."""

    @pytest.fixture(scope="class")
    async def main_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> Branch:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        await initialize_registry(db=db)
        default_branch_scope_class.update_schema_hash()
        return default_branch_scope_class

    @pytest.fixture(scope="class")
    async def pool_with_late_range(self, db: InfrahubDatabase, main_branch: Branch) -> tuple[CoreNumberPool, Branch]:
        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(db=db, name="late-range-pool", node="TestingTicket", node_attribute="ticket_id")
        await pool.save(db=db)
        await add_pool_range(db=db, pool=pool, start=1, end=10)

        branch = await create_branch(branch_name="late-range", db=db)

        await add_pool_range(db=db, pool=pool, start=100, end=200)
        ticket = await Node.init(db=db, schema=TICKET.kind)
        await ticket.new(db=db, title="late-ticket", ticket_id=5)
        await ticket.save(db=db)
        return pool, branch

    async def test_repository_reads_a_range_added_after_the_branch(
        self, db: InfrahubDatabase, pool_with_late_range: tuple[CoreNumberPool, Branch]
    ) -> None:
        pool, _ = pool_with_late_range

        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())

        assert [(item.start.value, item.end.value) for item in ranges] == [(1, 10), (100, 200)]

    async def test_branch_reads_a_range_added_after_the_branch(
        self, db: InfrahubDatabase, pool_with_late_range: tuple[CoreNumberPool, Branch]
    ) -> None:
        pool, branch = pool_with_late_range

        ranges = await NodeManager.query(
            db=db, schema=CoreNumberPoolRange, filters={"pool__ids": [pool.get_id()]}, branch=branch
        )

        assert sorted((item.start.value, item.end.value) for item in ranges) == [(1, 10), (100, 200)]
        assert await NodeManager.query(db=db, schema=TICKET.kind, branch=branch) == []
