from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import get_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
    get_migration_console,
)

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

console = get_migration_console()

IP_POOL_KINDS = {InfrahubKind.IPADDRESSPOOL, InfrahubKind.IPPREFIXPOOL}


class Migration061(MigrationRequiringRebase):
    """Migrate IP pool-sourced relationships on templates to _from_resource_pool relationships."""

    name: str = "061_template_ip_pool_relationship_cleanup"
    minimum_version: int = 60

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)
        schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        return await self._process_templates(
            db=db, branch=default_branch, schema_branch=schema_branch, migration_input=migration_input
        )

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        db = migration_input.db
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)
        return await self._process_templates(
            db=db, branch=branch, schema_branch=schema_branch, migration_input=migration_input
        )

    async def _process_templates(
        self, db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch, migration_input: MigrationInput
    ) -> MigrationResult:
        try:
            for template_kind in schema_branch.template_names:
                template_schema = schema_branch.get(name=template_kind, duplicate=False)

                # Build map: original_rel_name -> pool_rel_name
                pool_rel_map: dict[str, str] = {}
                for rel in template_schema.relationships:
                    if rel.name.endswith("_from_resource_pool"):
                        original_name = rel.name.removesuffix("_from_resource_pool")
                        if original_name in template_schema.relationship_names:
                            pool_rel_map[original_name] = rel.name

                if not pool_rel_map:
                    continue

                templates = await NodeManager.query(
                    db=db,
                    schema=template_kind,
                    branch=branch,
                    include_metadata=MetadataOptions.LINKED_NODES,
                )

                for template in templates:
                    await self._process_one_template(
                        db=db, template=template, pool_rel_map=pool_rel_map, migration_input=migration_input
                    )

        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__}: {repr(exc)}"
            return MigrationResult(errors=[error_msg])

        return MigrationResult()

    async def _process_one_template(
        self, db: InfrahubDatabase, template: Node, pool_rel_map: dict[str, str], migration_input: MigrationInput
    ) -> None:
        at = migration_input.at
        user_id = migration_input.user_id

        for original_rel_name, pool_rel_name in pool_rel_map.items():
            rel_mgr = template.get_relationship(original_rel_name)

            # Find the first relationship sourced from an IP pool (at most one per manager)
            rels = await rel_mgr.get_relationships(db=db)
            for rel in rels:
                if not getattr(rel, "source_id", None):
                    continue
                source = await rel.get_source(db=db)
                if not source or source.get_kind() not in IP_POOL_KINDS:
                    continue

                # Create _from_resource_pool relationship pointing to the pool
                pool_rel_mgr = template.get_relationship(pool_rel_name)
                await pool_rel_mgr.update(db=db, data=source)
                await pool_rel_mgr.save(db=db, at=at, user_id=user_id)

                # Soft-delete the original pool-sourced relationship
                await rel.delete(db=db, at=at, user_id=user_id)
                break
