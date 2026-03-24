from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.migrations.shared import MigrationInput, MigrationResult, get_migration_console
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema.definitions.internal import (
    generic_schema as internal_generic_schema,
)
from infrahub.core.schema.definitions.internal import (
    node_schema as internal_node_schema,
)
from infrahub.core.schema.manager import SchemaManager
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

log = get_logger()
console = get_migration_console()


async def update_schema_on_branch(db: InfrahubDatabase, branch: Branch, at: Timestamp, user_id: str) -> None:
    """Update SchemaNode and SchemaGeneric on a specific branch."""
    # Load schema for this branch
    manager = SchemaManager()
    registry.schema = manager
    internal_schema_root = SchemaRoot(**internal_schema)
    manager.register_schema(schema=internal_schema_root)
    schema_branch = await manager.load_schema_from_db(db=db, branch=branch)

    node_kind = "SchemaNode"
    node_schema = schema_branch.get_node(name=node_kind, duplicate=False)
    node_schema_node = await manager.get_one(db=db, branch=branch, id=node_schema.get_id(), prefetch_relationships=True)
    current_node_schema = await manager.convert_node_schema_to_schema(db=db, schema_node=node_schema_node)

    generic_kind = "SchemaGeneric"
    generic_schema = schema_branch.get_node(name=generic_kind, duplicate=False)
    generic_schema_node = await manager.get_one(
        db=db, branch=branch, id=generic_schema.get_id(), prefetch_relationships=True
    )
    current_generic_schema = await manager.convert_node_schema_to_schema(db=db, schema_node=generic_schema_node)

    for current_schema, internal_schema_spec in [
        (current_node_schema, internal_node_schema),
        (current_generic_schema, internal_generic_schema),
    ]:
        # Update SchemaNode
        changed = False
        if current_schema.human_friendly_id != internal_schema_spec.human_friendly_id:
            current_schema.human_friendly_id = internal_schema_spec.human_friendly_id
            changed = True
        if current_schema.uniqueness_constraints != internal_schema_spec.uniqueness_constraints:
            current_schema.uniqueness_constraints = internal_schema_spec.uniqueness_constraints
            changed = True

        # Update the name attribute to be unique = False
        name_attr = current_schema.get_attribute(name="name")
        if name_attr.unique:
            name_attr.unique = False
            changed = True

        if changed:
            # Save SchemaNode back to DB
            await manager.update_node_in_db(
                db=db,
                node=current_schema,
                user_id=user_id,
                at=at,
                branch=branch,
            )


class Migration056(ArbitraryMigration):
    name: str = "056_update_schema_node_generic_constraints"
    minimum_version: int = 55

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        user_id = migration_input.user_id

        console.log("[bold]Updating SchemaNode and SchemaGeneric constraints[/bold]")

        # Get default branch
        default_branch = registry.get_branch_from_registry()
        console.log(f"Updating on default branch: {default_branch.name}")
        await update_schema_on_branch(db=db, branch=default_branch, at=at, user_id=user_id)

        branches = await Branch.get_list(db=db)
        branches = [b for b in branches if not b.is_default and not b.is_global]
        console.log(f"Found {len(branches)} branches to update")
        for branch in branches:
            console.log(f"Updating on branch: {branch.name}")
            await update_schema_on_branch(db=db, branch=branch, at=at, user_id=user_id)

        console.log("[bold green]Migration completed successfully[/bold green]")
        return MigrationResult()
