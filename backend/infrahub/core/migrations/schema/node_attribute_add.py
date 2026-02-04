from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core import registry
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.log import get_logger
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.tasks.registry import update_branch_registry

from ..query import AttributeMigrationQuery, MigrationBaseQuery
from ..query.attribute_add import AttributeAddQuery
from ..shared import AttributeSchemaMigration, MigrationInput, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.database import InfrahubDatabase

    from ...branch import Branch

log = get_logger()


class NodeAttributeAddMigrationQuery01(AttributeMigrationQuery, AttributeAddQuery):
    name = "migration_node_attribute_add_01"

    def _get_node_kinds(self, schema: MainSchemaTypes, new_attribute_schema: AttributeSchema) -> list[str]:
        schema_kinds = [schema.kind]
        if not isinstance(schema, (NodeSchema, GenericSchema)):
            return schema_kinds
        if new_attribute_schema.support_profiles:
            schema_kinds.append(f"Profile{schema.kind}")
            if isinstance(schema, GenericSchema) and schema.used_by:
                schema_kinds.extend([f"Profile{kind}" for kind in schema.used_by])
        if new_attribute_schema.support_templates:
            schema_kinds.append(f"Template{schema.kind}")
            if isinstance(schema, GenericSchema) and schema.used_by:
                schema_kinds.extend([f"Template{kind}" for kind in schema.used_by])
        return schema_kinds

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        node_kinds = self._get_node_kinds(
            schema=migration.new_schema, new_attribute_schema=migration.new_attribute_schema
        )
        super().__init__(
            migration=migration,
            node_kinds=node_kinds,
            attribute_name=migration.new_attribute_schema.name,
            attribute_kind=migration.new_attribute_schema.kind,
            branch_support=migration.new_attribute_schema.get_branch().value,
            default_value=migration.new_attribute_schema.default_value,
            **kwargs,
        )


class NodeAttributeAddMigration(AttributeSchemaMigration):
    name: str = "node.attribute.add"
    queries: Sequence[type[AttributeMigrationQuery]] = [NodeAttributeAddMigrationQuery01]  # type: ignore[assignment]

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        if self.new_attribute_schema.inherited is True:
            return MigrationResult()
        return await super().execute(migration_input=migration_input, branch=branch, queries=queries)

    async def execute_post_queries(
        self,
        migration_input: MigrationInput,
        result: MigrationResult,
        branch: Branch,
    ) -> MigrationResult:
        if self.new_attribute_schema.kind != "NumberPool":
            return result

        db = migration_input.db
        at = migration_input.at

        # Use SchemaNumberPoolSynchronizer to create/find the number pool
        synchronizer = SchemaNumberPoolSynchronizer(
            db=db,
            log=log,
            schema_manager=registry.schema,
        )
        pool_id = await synchronizer.ensure_pool_for_attribute(
            schema_node=self.new_schema,
            attribute=self.new_attribute_schema,
            at=at,
        )

        # Fetch the pool object to allocate numbers
        number_pool = await registry.manager.get_one_by_id_or_default_filter(db=db, id=pool_id, kind=CoreNumberPool)

        await update_branch_registry(db=db, branch=branch)

        nodes: list[Node] = await registry.manager.query(
            db=db, branch=branch, schema=self.new_schema, fields={"id": True, self.new_attribute_schema.name: True}
        )

        async def allocate_numbers(db: InfrahubDatabase) -> None:
            for node in nodes:
                number = await number_pool.get_resource(  # type: ignore[attr-defined]
                    db=db, branch=branch, node=node, attribute=self.new_attribute_schema, at=at
                )
                attr = node.get_attribute(name=self.new_attribute_schema.name)
                attr.value = number
                attr.set_source(number_pool.get_id())

                await node.save(db=db, fields=[self.new_attribute_schema.name], at=at)

        if db.is_transaction:
            await allocate_numbers(db=db)
        else:
            async with db.start_transaction() as dbt:
                await allocate_numbers(db=dbt)

        return result
