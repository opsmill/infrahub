from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from rich.console import Console

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

POOL_PAGE_SIZE = 100
RANGES_RELATIONSHIP_NAME = "ranges"


class Migration079(ArbitraryMigration):
    """Give every number pool the range it allocates from.

    A number pool carries its bounds as a pair of attributes. Those bounds now live on range nodes
    so a pool can hold several of them, and the pair stays behind as a deprecated mirror of the
    bounds of a pool holding exactly one range.

    Graph migrations run before the core schema update, so the range kind and the pool's
    relationship to it are written into the database schema here, before any range node is
    created. A pool that holds no range and still carries both bounds receives one range spanning
    them, with no weight, after which the shorthand mirrors that range. A pool that already holds
    a range is left alone, so a second run creates nothing.
    """

    name: str = "079_number_pool_ranges"
    description: str = "Materialise one range per existing number pool and mirror it onto the deprecated shorthand"
    minimum_version: int = 78

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        """Report the pools whose bounds never reached a range.

        A pool that carries no bounds cannot produce a range and is legal on its own, so only a
        pool that still declares both bounds without holding a range counts as unmigrated.
        """
        result = MigrationResult()

        default_branch = await self._prepare_schema(db=db)
        unmigrated = 0
        async for pool in self._iter_pools(db=db, branch=default_branch):
            if self._bounds_of(pool=pool) is None:
                continue
            if not await pool.load_ranges(db=db):
                unmigrated += 1

        if unmigrated:
            result.errors.append(f"{unmigrated} number pool(s) still carry bounds without a range")

        return result

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console
        result = MigrationResult()

        try:
            default_branch = await self._bootstrap_schema(
                db=db, at=migration_input.at, user_id=migration_input.user_id, console=console
            )
        # The migration cannot create a single range without the kind, so this failure ends the run.
        except Exception as exc:  # noqa: BLE001
            console.log(f"Unable to add the number pool range kind to the schema: {exc}")
            return MigrationResult(errors=[f"adding the number pool range kind to the schema: {exc}"])

        async for pool in self._iter_pools(db=db, branch=default_branch):
            # One unconvertible pool must not hide the state of every pool after it.
            try:
                created = await self._migrate_pool(db=db, pool=pool, at=migration_input.at)
            except Exception as exc:  # noqa: BLE001
                console.log(f"Unable to create the range of number pool {pool.get_id()}: {exc}")
                result.errors.append(f"creating the range of number pool {pool.get_id()}: {exc}")
            else:
                if created:
                    result.nbr_migrations_executed += 1

        console.log(f"Created {result.nbr_migrations_executed} number pool range(s) from the existing bounds.")
        return result

    async def _bootstrap_schema(self, db: InfrahubDatabase, at: Timestamp, user_id: str, console: Console) -> Branch:
        """Put the range kind and the pool's ranges relationship into the database schema.

        Returns:
            The default branch, which every pool and range belongs to.

        """
        default_branch = await self._prepare_registry(db=db)
        db_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

        candidate = db_schema.duplicate()
        candidate.load_schema(schema=SchemaRoot(**internal_schema))
        candidate.load_schema(schema=SchemaRoot(**core_models))
        candidate.process()

        bootstrap_needed = not self._schema_carries_ranges(schema=db_schema)
        if bootstrap_needed:
            console.log(f"  Adding {InfrahubKind.NUMBERPOOLRANGE} and the pool's ranges relationship to the schema.")
        await registry.schema.update_schema_branch(
            schema=candidate,
            db=db,
            branch=default_branch,
            limit=[InfrahubKind.NUMBERPOOL, InfrahubKind.NUMBERPOOLRANGE],
            update_db=bootstrap_needed,
            at=at,
            user_id=user_id,
        )
        return default_branch

    async def _prepare_schema(self, db: InfrahubDatabase) -> Branch:
        """Load the database schema into the registry so the Node API can reach pools and ranges.

        Returns:
            The default branch, which every pool and range belongs to.

        """
        default_branch = await self._prepare_registry(db=db)
        db_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        db_schema.load_schema(schema=SchemaRoot(**internal_schema))
        db_schema.process()
        registry.schema.set_schema_branch(name=default_branch.name, schema=db_schema)
        return default_branch

    @staticmethod
    async def _prepare_registry(db: InfrahubDatabase) -> Branch:
        if not registry.schema_has_been_initialized():
            registry.schema = SchemaManager()
            registry.schema.register_schema(schema=SchemaRoot(**internal_schema))
        return await registry.get_branch(branch=registry.default_branch, db=db)

    @staticmethod
    def _schema_carries_ranges(schema: SchemaBranch) -> bool:
        if not schema.has(name=InfrahubKind.NUMBERPOOL) or not schema.has(name=InfrahubKind.NUMBERPOOLRANGE):
            return False
        pool_schema = schema.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False)
        return any(relationship.name == RANGES_RELATIONSHIP_NAME for relationship in pool_schema.relationships)

    @staticmethod
    def _bounds_of(pool: CoreNumberPool) -> tuple[int, int] | None:
        """Return the pool's shorthand bounds, or None when it does not declare both."""
        start = pool.start_range.value  # type: ignore[attr-defined]
        end = pool.end_range.value  # type: ignore[attr-defined]
        if start is None or end is None:
            return None
        return int(start), int(end)

    async def _migrate_pool(self, db: InfrahubDatabase, pool: CoreNumberPool, at: Timestamp) -> bool:
        """Give one pool the range its bounds describe.

        Returns:
            Whether a range was created.

        """
        if await pool.load_ranges(db=db):
            return False

        bounds = self._bounds_of(pool=pool)
        if bounds is None:
            return False

        start, end = bounds
        pool_range = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOLRANGE)
        await pool_range.new(db=db, start=start, end=end, pool=pool.get_id())
        await pool_range.save(db=db, at=at)

        await pool.sync_shorthand_from_ranges(db=db)
        return True

    @staticmethod
    async def _iter_pools(db: InfrahubDatabase, branch: Branch) -> AsyncIterator[CoreNumberPool]:
        """Walk every live number pool one page at a time."""
        offset = 0
        while True:
            page = await registry.manager.query(
                db=db,
                schema=InfrahubKind.NUMBERPOOL,
                branch=branch,
                branch_agnostic=True,
                offset=offset,
                limit=POOL_PAGE_SIZE,
            )
            for node in page:
                if isinstance(node, CoreNumberPool):
                    yield node
            if len(page) < POOL_PAGE_SIZE:
                return
            offset += POOL_PAGE_SIZE
