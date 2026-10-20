from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.models import HashableModelDiff
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.protocols import CoreNumberPoolRange
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.pools.number_pool_repository import NumberPoolRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from rich.console import Console

    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

POOL_PAGE_SIZE = 100
RANGES_RELATIONSHIP_NAME = "ranges"


class Migration080(ArbitraryMigration):
    """Give every number pool the range it allocates from.

    A number pool carries its bounds as a pair of attributes. Those bounds now live on range nodes
    so a pool can hold several of them, and the pair stays behind as a deprecated mirror of the
    bounds of a pool holding exactly one range.

    Graph migrations run before the core schema update, so the range kind and the pool's
    relationship to it are written into the database schema here, before any range node is
    created. A pool that holds no range and carries a bound receives one range spanning its bounds,
    with no weight, a missing start resolving to 1 and a missing end to the largest integer. The
    shorthand is left as it is. A pool that already holds a range is left alone, so a second run
    creates nothing.
    """

    name: str = "080_number_pool_ranges"
    description: str = "Materialise one range per existing number pool from its bounds"
    minimum_version: int = 79

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        """Report the pools whose bounds never reached a range.

        A pool that carries no bound cannot produce a range and is legal on its own. Any pool that
        carries a bound, whatever its value, and holds no range counts as unmigrated, including one
        the run failed to convert.
        """
        result = MigrationResult()

        default_branch = await self._prepare_schema(db=db)
        repository = NumberPoolRepository(db=db)
        unmigrated = 0
        try:
            async for pool in self._iter_pools(db=db, branch=default_branch):
                if not self._carries_a_bound(pool=pool):
                    continue
                if not await repository.get_ranges(pool_id=pool.get_id()):
                    unmigrated += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"reading the number pools: {_describe(exc)}")
            return result

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
            console.log(f"Unable to add the number pool range kind to the schema: {_describe(exc)}")
            return MigrationResult(errors=[f"adding the number pool range kind to the schema: {_describe(exc)}"])

        # A failed page read ends the walk; the ranges created before it stay counted.
        try:
            async for pool in self._iter_pools(db=db, branch=default_branch):
                # One unconvertible pool must not hide the state of every pool after it.
                try:
                    created = await self._migrate_pool(
                        db=db, pool=pool, at=migration_input.at, user_id=migration_input.user_id, console=console
                    )
                except Exception as exc:  # noqa: BLE001
                    console.log(f"Unable to create the range of number pool {pool.get_id()}: {_describe(exc)}")
                    result.errors.append(f"creating the range of number pool {pool.get_id()}: {_describe(exc)}")
                else:
                    if created:
                        result.nbr_migrations_executed += 1
        except Exception as exc:  # noqa: BLE001
            console.log(f"Unable to read the number pools: {_describe(exc)}")
            result.errors.append(f"reading the number pools: {_describe(exc)}")

        console.log(f"Created {result.nbr_migrations_executed} number pool range(s) from the existing bounds.")
        return result

    async def _bootstrap_schema(self, db: InfrahubDatabase, at: Timestamp, user_id: str, console: Console) -> Branch:
        """Put the range kind and the pool's ranges relationship into the database schema.

        Only those two definitions are written. Every other difference between the stored pool
        schema and the code is left for the core schema update, which runs after the graph
        migrations and applies the schema migrations those differences need.

        Returns:
            The default branch, which every pool and range belongs to.

        """
        default_branch = await self._prepare_registry(db=db)
        db_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

        code_schema = db_schema.duplicate()
        code_schema.load_schema(schema=SchemaRoot(**internal_schema))
        code_schema.load_schema(schema=SchemaRoot(**core_models))
        code_schema.process()

        if not db_schema.has(name=InfrahubKind.NUMBERPOOLRANGE):
            console.log(f"  Adding {InfrahubKind.NUMBERPOOLRANGE} to the schema.")
            await registry.schema.create_node_in_db(
                node=code_schema.get_node(name=InfrahubKind.NUMBERPOOLRANGE),
                db=db,
                branch=default_branch,
                at=at,
                user_id=user_id,
            )

        stored_pool = db_schema.get_node(name=InfrahubKind.NUMBERPOOL)
        if not any(relationship.name == RANGES_RELATIONSHIP_NAME for relationship in stored_pool.relationships):
            console.log(f"  Adding the ranges relationship of {InfrahubKind.NUMBERPOOL} to the schema.")
            ranges_relationship = code_schema.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False).get_relationship(
                name=RANGES_RELATIONSHIP_NAME
            )
            stored_pool.relationships.append(ranges_relationship.duplicate())
            await registry.schema.update_node_in_db_based_on_diff(
                db=db,
                diff=HashableModelDiff(
                    changed={"relationships": HashableModelDiff(added={RANGES_RELATIONSHIP_NAME: None})}
                ),
                node=stored_pool,
                branch=default_branch,
                at=at,
                user_id=user_id,
            )

        await self._prepare_schema(db=db)
        if default_branch.update_schema_hash():
            await default_branch.save(db=db)
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
    def _carries_a_bound(pool: CoreNumberPool) -> bool:
        return pool.get_attribute("start_range").value is not None or pool.get_attribute("end_range").value is not None

    @staticmethod
    def _range_bounds(pool: CoreNumberPool) -> tuple[int, int] | None:
        """Return the bounds of the range the pool's shorthand describes, or None when it declares no bound.

        Raises:
            ValueError: When a declared bound is not an integer.

        """
        start = pool.get_attribute("start_range").value
        end = pool.get_attribute("end_range").value
        if start is None and end is None:
            return None
        if isinstance(start, int | None) and isinstance(end, int | None):
            return (1 if start is None else start, sys.maxsize if end is None else end)
        raise ValueError(f"number pool {pool.get_id()} carries a bound that is not an integer")

    async def _migrate_pool(
        self, db: InfrahubDatabase, pool: CoreNumberPool, at: Timestamp, user_id: str, console: Console
    ) -> bool:
        """Give one pool the range its bounds describe.

        Returns:
            Whether a range was created.

        """
        repository = NumberPoolRepository(db=db)
        if await repository.get_ranges(pool_id=pool.get_id()):
            return False

        bounds = self._range_bounds(pool=pool)
        if bounds is None:
            console.log(f"  Skipping number pool {pool.get_id()}: it declares no bound, so it gets no range.")
            return False

        start, end = bounds
        pool_range = await Node.init(db=db, schema=CoreNumberPoolRange)
        await pool_range.new(db=db, start=start, end=end, pool=pool.get_id())
        await pool_range.save(db=db, at=at, user_id=user_id)
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


def _describe(exc: Exception) -> str:
    return str(exc) or f"{type(exc).__name__}: {exc!r}"
