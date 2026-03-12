from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import NULL_VALUE, InfrahubKind, MetadataOptions
from infrahub.core.initialization import get_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.update_attribute_values import UpdateAttributeValuesQuery
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
    get_migration_console,
)

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

console = get_migration_console()


class Migration063(MigrationRequiringRebase):
    """Nullify attribute values on template nodes where the source is a CoreNumberPool."""

    name: str = "063_template_number_pool_cleanup"
    minimum_version: int = 62

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)
        schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)
        return await self._process_templates(db=db, branch=default_branch, schema_branch=schema_branch)

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        db = migration_input.db
        schema_branch = await get_or_load_schema_branch(db=db, branch=branch)
        return await self._process_templates(db=db, branch=branch, schema_branch=schema_branch)

    async def _process_templates(
        self, db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch
    ) -> MigrationResult:
        try:
            for template_kind in schema_branch.template_names:
                template_schema = schema_branch.get(name=template_kind, duplicate=False)

                templates = await NodeManager.query(
                    db=db,
                    schema=template_kind,
                    branch=branch,
                    include_metadata=MetadataOptions.LINKED_NODES,
                )

                # Collect node IDs to nullify, grouped by attribute name
                nullify_map: dict[str, set[str]] = defaultdict(set)

                for template in templates:
                    attr_names_to_nullify = await self._collect_pool_sourced_attrs(
                        db=db, template=template, template_schema=template_schema
                    )
                    for attr_name in attr_names_to_nullify:
                        nullify_map[attr_name].add(template.id)

                # Write updates via UpdateAttributeValuesQuery (bypasses ORM validation)
                for attr_name, node_ids in nullify_map.items():
                    attr_schema = template_schema.get_attribute(attr_name)
                    values_by_id = dict.fromkeys(node_ids, NULL_VALUE)
                    query = await UpdateAttributeValuesQuery.init(
                        db=db, branch=branch, attribute_schema=attr_schema, values_by_id_map=values_by_id
                    )
                    await query.execute(db=db)

        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__}: {repr(exc)}"
            return MigrationResult(errors=[error_msg])

        return MigrationResult()

    async def _collect_pool_sourced_attrs(
        self,
        db: InfrahubDatabase,
        template: Node,
        template_schema: MainSchemaTypes,
    ) -> list[str]:
        attrs_to_nullify: list[str] = []
        for attr_schema in template_schema.attributes:
            attribute = template.get_attribute(attr_schema.name)
            if not attribute or not getattr(attribute, "source_id", None):
                continue
            source = await attribute.get_source(db=db)
            if not source or source.get_kind() != InfrahubKind.NUMBERPOOL:
                continue
            if attribute.value is not None and attribute.value != NULL_VALUE:
                attrs_to_nullify.append(attr_schema.name)
        return attrs_to_nullify
