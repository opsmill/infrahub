from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
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


class Migration063(MigrationRequiringRebase):
    """Migrate pool-sourced relationships and attributes on templates to _from_resource_pool relationships.

    Handles two cases:
    1. IP relationships sourced from IP pools → creates _from_resource_pool relationship, deletes original
    2. Number attributes sourced from Number pools → creates _from_resource_pool relationship, clears attribute source
    """

    name: str = "063_template_pool_relationship_cleanup"
    minimum_version: int = 62

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

                # Build map: original_rel_name -> pool_rel_name (for IP relationships)
                rel_pool_map: dict[str, str] = {}
                # Build map: attr_name -> pool_rel_name (for Number attributes)
                attr_pool_map: dict[str, str] = {}

                for rel in template_schema.relationships:
                    if not rel.name.endswith(RESOURCE_POOL_REL_SUFFIX):
                        continue
                    original_name = rel.name.removesuffix(RESOURCE_POOL_REL_SUFFIX)
                    if original_name in template_schema.relationship_names:
                        rel_pool_map[original_name] = rel.name
                    elif original_name in template_schema.attribute_names:
                        attr_pool_map[original_name] = rel.name

                if not rel_pool_map and not attr_pool_map:
                    continue

                templates = await NodeManager.query(
                    db=db,
                    schema=template_kind,
                    branch=branch,
                    include_metadata=MetadataOptions.LINKED_NODES,
                )

                for template in templates:
                    await self._process_one_template(
                        db=db,
                        template=template,
                        rel_pool_map=rel_pool_map,
                        attr_pool_map=attr_pool_map,
                        migration_input=migration_input,
                    )

        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__}: {repr(exc)}"
            return MigrationResult(errors=[error_msg])

        return MigrationResult()

    async def _process_one_template(
        self,
        db: InfrahubDatabase,
        template: Node,
        rel_pool_map: dict[str, str],
        attr_pool_map: dict[str, str],
        migration_input: MigrationInput,
    ) -> None:
        at = migration_input.at
        user_id = migration_input.user_id

        # Handle IP relationship pool sources
        for original_rel_name, pool_rel_name in rel_pool_map.items():
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

        # Handle Number attribute pool sources
        for attr_name, pool_rel_name in attr_pool_map.items():
            attribute = template.get_attribute(attr_name)
            if not attribute or not getattr(attribute, "source_id", None):
                continue

            source = await attribute.get_source(db=db)
            if not source or source.get_kind() != InfrahubKind.NUMBERPOOL:
                continue

            # Check if _from_resource_pool relationship already exists (idempotency)
            pool_rel_mgr = template.get_relationship(pool_rel_name)
            existing_pool_rels = await pool_rel_mgr.get_relationships(db=db)
            if existing_pool_rels:
                continue

            # Create _from_resource_pool relationship pointing to the pool
            await pool_rel_mgr.update(db=db, data=source)
            await pool_rel_mgr.save(db=db, at=at, user_id=user_id)

            # Clear the attribute source
            attribute.clear_source()
            await attribute.save(db=db, at=at, user_id=user_id)
