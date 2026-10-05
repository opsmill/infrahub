import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.number_pool import add_pool_range, shorthand_mirror
from tests.helpers.schema import TICKET, load_schema


async def _reload(db: InfrahubDatabase, pool: CoreNumberPool) -> CoreNumberPool:
    reloaded = await NodeManager.get_one(db=db, id=pool.get_id(), kind=InfrahubKind.NUMBERPOOL, raise_on_error=True)
    assert isinstance(reloaded, CoreNumberPool)
    return reloaded


class TestNumberPoolShorthandMirror:
    """The ticket schema is loaded once for the class; every test mirrors a pool of its own."""

    @pytest.fixture(scope="class")
    async def ticket_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        await initialize_registry(db=db)

    async def test_sync_shorthand_from_ranges(self, db: InfrahubDatabase, ticket_schema: None) -> None:
        """The shorthand carries the bounds of a single range and is null for any other range count."""
        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(
            db=db,
            name="mirror-from-ranges",
            node="TestingTicket",
            node_attribute="ticket_id",
            start_range=1,
            end_range=10,
        )
        await pool.save(db=db)

        await shorthand_mirror(db=db).sync(pool=pool)
        assert pool.start_range.value is None
        assert pool.end_range.value is None

        await add_pool_range(db=db, pool=pool, start=100, end=200)
        await shorthand_mirror(db=db).sync(pool=pool)
        assert pool.start_range.value == 100
        assert pool.end_range.value == 200

        await add_pool_range(db=db, pool=pool, start=300, end=400)
        await shorthand_mirror(db=db).sync(pool=pool)
        assert pool.start_range.value is None
        assert pool.end_range.value is None

        reloaded = await _reload(db=db, pool=pool)
        assert reloaded.start_range.value is None
        assert reloaded.end_range.value is None

    async def test_sync_shorthand_writes_only_the_shorthand_at_the_given_time(
        self, db: InfrahubDatabase, ticket_schema: None
    ) -> None:
        """The mirror saves the two shorthand attributes at the caller's timestamp and nothing else."""
        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(
            db=db,
            name="mirror-at-given-time",
            node="TestingTicket",
            node_attribute="ticket_id",
            start_range=1,
            end_range=10,
        )
        await pool.save(db=db)
        await add_pool_range(db=db, pool=pool, start=100, end=200)

        sync_at = Timestamp()
        pool.description.value = "pending change owned by another writer"
        await shorthand_mirror(db=db).sync(pool=pool, at=sync_at)

        at_sync = await NodeManager.get_one(db=db, id=pool.get_id(), at=sync_at)
        assert at_sync is not None
        assert (at_sync.get_attribute("start_range").value, at_sync.get_attribute("end_range").value) == (100, 200)

        reloaded = await _reload(db=db, pool=pool)
        assert reloaded.description.value is None

    async def test_sync_shorthand_records_the_caller_and_leaves_a_correct_mirror_untouched(
        self, db: InfrahubDatabase, ticket_schema: None
    ) -> None:
        """The write is recorded under the caller's account, and a mirror that is already right is not rewritten."""
        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(
            db=db,
            name="mirror-records-caller",
            node="TestingTicket",
            node_attribute="ticket_id",
            start_range=1,
            end_range=10,
        )
        await pool.save(db=db)
        await add_pool_range(db=db, pool=pool, start=100, end=200)

        sync_at = Timestamp()
        await shorthand_mirror(db=db).sync(pool=pool, at=sync_at, user_id="first-writer")

        async def shorthand_metadata() -> list[tuple[str | None, str | None]]:
            loaded = await NodeManager.get_one(
                db=db, id=pool.get_id(), include_metadata=MetadataOptions.USER_TIMESTAMPS
            )
            assert loaded is not None
            metadata = []
            for name in ("start_range", "end_range"):
                attribute = loaded.get_attribute(name)
                updated_at = attribute._get_updated_at()
                metadata.append((attribute._get_updated_by(), updated_at.to_string() if updated_at else None))
            return metadata

        assert await shorthand_metadata() == [
            ("first-writer", sync_at.to_string()),
            ("first-writer", sync_at.to_string()),
        ]

        reloaded = await _reload(db=db, pool=pool)
        await shorthand_mirror(db=db).sync(pool=reloaded, at=Timestamp(), user_id="second-writer")

        assert await shorthand_metadata() == [
            ("first-writer", sync_at.to_string()),
            ("first-writer", sync_at.to_string()),
        ]

    async def test_sync_shorthand_mirrors_the_ranges_the_caller_holds(
        self, db: InfrahubDatabase, ticket_schema: None
    ) -> None:
        """Ranges handed in by the caller are mirrored as given, without reading the pool's ranges again."""
        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(
            db=db,
            name="mirror-caller-ranges",
            node="TestingTicket",
            node_attribute="ticket_id",
            start_range=1,
            end_range=10,
        )
        await pool.save(db=db)
        held_range = await add_pool_range(db=db, pool=pool, start=100, end=200)
        await add_pool_range(db=db, pool=pool, start=300, end=400)

        await shorthand_mirror(db=db).sync(pool=pool, ranges=[held_range])

        reloaded = await _reload(db=db, pool=pool)
        assert (reloaded.start_range.value, reloaded.end_range.value) == (100, 200)
