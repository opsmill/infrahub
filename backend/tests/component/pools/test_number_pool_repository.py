import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.initialization import initialize_registry
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetTaken, NumberPoolGetUsed, PoolRecordProvenance
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from tests.helpers.agnostic_edges import TEST_ACTOR_ID, VertexMetadata, node_metadata, pool_reservation_edges
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

SECOND_ACTOR_ID = "5b7d2e0c-4f3a-4c1e-9a6b-2d8f1c0e7a41"
"""A second named account, so a write attributed to the wrong actor is distinguishable from one attributed to none."""


async def _pool(db: InfrahubDatabase, name: str) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name=name, node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await pool.save(db=db)
    return pool


async def _ticket_attribute_id(db: InfrahubDatabase, title: str, ticket_id: int) -> tuple[str, str]:
    """A ticket holding a hand-set number no pool tracks, with the id of its number attribute vertex."""
    ticket = await Node.init(db=db, schema=TICKET.kind)
    await ticket.new(db=db, title=title, ticket_id=ticket_id)
    await ticket.save(db=db)
    attribute_id = ticket.get_attribute("ticket_id").id
    assert attribute_id is not None
    return ticket.get_id(), attribute_id


class TestNumberPoolRepository:
    """Reads and writes of the number pool repository against the real database.

    The schema is loaded once for the class and pools and tickets accumulate across tests, so every test
    uses pools and tickets of its own.
    """

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

    async def test_get_ranges(self, db: InfrahubDatabase, main_branch: Branch) -> None:
        """The pool's ranges come back lowest start first, whatever order they were created in."""
        pool = await _pool(db=db, name="pool1")

        assert await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id()) == []

        second = await add_pool_range(db=db, pool=pool, start=300, end=400)
        first = await add_pool_range(db=db, pool=pool, start=100, end=200)

        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
        assert [(item.start.value, item.end.value) for item in ranges] == [(100, 200), (300, 400)]
        assert [item.get_id() for item in ranges] == [first.get_id(), second.get_id()]

    async def test_an_empty_space_reads_no_used_or_taken_number_without_querying(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """A space holding no segment answers the used and taken reads without running their queries."""
        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(db=db, name="empty-pool", node="TestingTicket", node_attribute="ticket_id")
        await pool.save(db=db)
        counting_db = CountingInfrahubDatabase.from_db(db=db)
        repository = NumberPoolRepository(db=counting_db)
        space = EffectiveSpace(ranges=[], domain=NumberDomain())

        assert await repository.get_used(pool=pool, branch=main_branch, space=space) == []
        assert await repository.get_taken(pool=pool, branch=main_branch, space=space) == set()
        assert counting_db.count_for(NumberPoolGetUsed.name) == 0
        assert counting_db.count_for(NumberPoolGetTaken.name) == 0

    async def test_reserve_records_the_acting_account_on_the_record_and_the_pool(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """A record opens under the account that made it, and the pool shows that account as its last change."""
        pool = await _pool(db=db, name="reserve-actor")
        ticket_id, attribute_id = await _ticket_attribute_id(db=db, title="reserve-actor", ticket_id=1001)
        before = await node_metadata(db=db, node_id=pool.get_id())
        assert before.updated_by == SYSTEM_USER_ID
        at = Timestamp()

        await NumberPoolRepository(db=db).reserve(
            pool_id=pool.get_id(),
            identifier=ticket_id,
            attribute_id=attribute_id,
            provenance=PoolRecordProvenance.PROVIDED,
            at=at,
            user_id=TEST_ACTOR_ID,
        )

        [record] = await pool_reservation_edges(db=db, pool_id=pool.get_id(), attribute_id=attribute_id)
        assert (record.from_time, record.from_user_id, record.to_time, record.to_user_id) == (
            at.to_string(),
            TEST_ACTOR_ID,
            None,
            None,
        )
        assert await node_metadata(db=db, node_id=pool.get_id()) == VertexMetadata(
            updated_at=at.to_string(),
            updated_by=TEST_ACTOR_ID,
            previous_updated_at=before.updated_at,
            previous_updated_by=before.updated_by,
        )

    async def test_a_pool_taking_over_an_attribute_closes_the_other_pools_record_under_the_acting_account(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """Both pools changed, so both carry the second write's stamp, and the first keeps its own as the previous one."""
        first_pool = await _pool(db=db, name="takeover-first")
        second_pool = await _pool(db=db, name="takeover-second")
        ticket_id, attribute_id = await _ticket_attribute_id(db=db, title="takeover", ticket_id=1002)
        repository = NumberPoolRepository(db=db)
        first_at = Timestamp()
        await repository.reserve(
            pool_id=first_pool.get_id(),
            identifier=ticket_id,
            attribute_id=attribute_id,
            provenance=PoolRecordProvenance.PROVIDED,
            at=first_at,
            user_id=TEST_ACTOR_ID,
        )
        second_before = await node_metadata(db=db, node_id=second_pool.get_id())
        second_at = Timestamp()

        await repository.reserve(
            pool_id=second_pool.get_id(),
            identifier=ticket_id,
            attribute_id=attribute_id,
            provenance=PoolRecordProvenance.PROVIDED,
            at=second_at,
            user_id=SECOND_ACTOR_ID,
        )

        [closed] = await pool_reservation_edges(db=db, pool_id=first_pool.get_id(), attribute_id=attribute_id)
        assert (closed.from_user_id, closed.to_time, closed.to_user_id) == (
            TEST_ACTOR_ID,
            second_at.to_string(),
            SECOND_ACTOR_ID,
        )
        [opened] = await pool_reservation_edges(db=db, pool_id=second_pool.get_id(), attribute_id=attribute_id)
        assert (opened.from_time, opened.from_user_id, opened.to_time) == (
            second_at.to_string(),
            SECOND_ACTOR_ID,
            None,
        )
        assert await node_metadata(db=db, node_id=first_pool.get_id()) == VertexMetadata(
            updated_at=second_at.to_string(),
            updated_by=SECOND_ACTOR_ID,
            previous_updated_at=first_at.to_string(),
            previous_updated_by=TEST_ACTOR_ID,
        )
        assert await node_metadata(db=db, node_id=second_pool.get_id()) == VertexMetadata(
            updated_at=second_at.to_string(),
            updated_by=SECOND_ACTOR_ID,
            previous_updated_at=second_before.updated_at,
            previous_updated_by=second_before.updated_by,
        )

    async def test_restating_a_kept_record_leaves_the_record_and_the_pool_untouched(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """A write that keeps the pool's live record changes nothing, so it leaves no stamp either."""
        pool = await _pool(db=db, name="restate")
        ticket_id, attribute_id = await _ticket_attribute_id(db=db, title="restate", ticket_id=1003)
        repository = NumberPoolRepository(db=db)
        await repository.reserve(
            pool_id=pool.get_id(),
            identifier=ticket_id,
            attribute_id=attribute_id,
            provenance=PoolRecordProvenance.PROVIDED,
            at=Timestamp(),
            user_id=TEST_ACTOR_ID,
        )
        records_before = await pool_reservation_edges(db=db, pool_id=pool.get_id(), attribute_id=attribute_id)
        metadata_before = await node_metadata(db=db, node_id=pool.get_id())
        assert metadata_before.updated_by == TEST_ACTOR_ID

        await repository.reserve(
            pool_id=pool.get_id(),
            identifier=ticket_id,
            attribute_id=attribute_id,
            provenance=PoolRecordProvenance.PROVIDED,
            at=Timestamp(),
            user_id=SECOND_ACTOR_ID,
        )

        assert await pool_reservation_edges(db=db, pool_id=pool.get_id(), attribute_id=attribute_id) == records_before
        assert await node_metadata(db=db, node_id=pool.get_id()) == metadata_before
