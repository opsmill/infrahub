from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.models import HashableModelDiff
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager

if TYPE_CHECKING:
    from rich.console import Console

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

RANGES_RELATIONSHIP_NAME = "ranges"


class Migration080(ArbitraryMigration):
    """Put the number pool range kind into the database schema.

    A number pool carries its bounds as a pair of attributes. Those bounds are moving onto range
    nodes so a pool can hold several of them. Graph migrations run before the core schema update,
    so the range kind and the pool's relationship to it are written into the database schema here,
    before any range node exists.
    """

    name: str = "080_number_pool_ranges"
    description: str = "Put the number pool range kind and the pool's ranges relationship into the database schema"
    minimum_version: int = 79

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        """Report a database schema that still lacks the range kind or the pool's ranges relationship."""
        result = MigrationResult()

        default_branch = await self._prepare_registry(db=db)
        db_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        if not self._schema_carries_ranges(schema=db_schema):
            result.errors.append("the database schema does not carry the number pool range kind")

        return result

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        console = migration_input.console
        result = MigrationResult()

        try:
            await self._bootstrap_schema(db=db, at=migration_input.at, user_id=migration_input.user_id, console=console)
        # The migration cannot create a single range without the kind, so this failure ends the run.
        except Exception as exc:  # noqa: BLE001
            console.log(f"Unable to add the number pool range kind to the schema: {exc}")
            return MigrationResult(errors=[f"adding the number pool range kind to the schema: {exc}"])

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
    def _schema_carries_ranges(schema: SchemaBranch) -> bool:
        if not schema.has(name=InfrahubKind.NUMBERPOOL) or not schema.has(name=InfrahubKind.NUMBERPOOLRANGE):
            return False
        pool_schema = schema.get_node(name=InfrahubKind.NUMBERPOOL, duplicate=False)
        return any(relationship.name == RANGES_RELATIONSHIP_NAME for relationship in pool_schema.relationships)
