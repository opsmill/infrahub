from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core import registry
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.log import get_logger
from infrahub.pools.existing_node_numbers import build_existing_node_number_allocator
from infrahub.pools.number_pool_locker import NumberPoolLock
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.tasks.registry import update_branch_registry

from ..query import AttributeMigrationQuery, MigrationBaseQuery
from ..query.attribute_add import AttributeAddQuery
from ..shared import AttributeSchemaMigration, MigrationInput, MigrationResult

if TYPE_CHECKING:
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
        if schema.check_if_attr_supports_profiles(attribute_schema=new_attribute_schema):
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
    queries: Sequence[type[MigrationBaseQuery]] = [NodeAttributeAddMigrationQuery01]
    force_inherited: bool = False

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        if self.new_attribute_schema.inherited is True and not self.force_inherited:
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

        # A migration can run on a worker still holding the schema from before the load, which the load already saved.
        await update_branch_registry(db=db, branch=branch)
        upserter = SchemaNumberPoolUpserter(
            db=db,
            schema_manager=registry.schema,
            range_store_factory=NumberPoolRepository,
        )
        number_pool = await upserter.upsert_number_pool(
            schema_node=self.new_schema,
            attribute=self.new_attribute_schema,
            branch_name=branch.name,
            at=at,
            user_id=migration_input.user_id,
        )

        await update_branch_registry(db=db, branch=branch)
        if not isinstance(number_pool, CoreNumberPool):
            raise TypeError(f"expected a number pool node for {self.new_schema.kind}.{self.new_attribute_schema.name}")

        async def allocate_numbers(db: InfrahubDatabase) -> None:
            allocator = build_existing_node_number_allocator(db=db, branch=branch)
            node_query = await NodeGetListQuery.init(db=db, schema=self.new_schema, branch=branch)
            await node_query.execute(db=db)
            async with NumberPoolLock(db=db).changing(pool_id=number_pool.get_id(), pool_name=number_pool.name.value):
                await allocator.allocate(
                    pool=number_pool,
                    attribute=self.new_attribute_schema,
                    kind=self.new_schema.kind,
                    node_ids=node_query.get_node_ids(),
                    branch=branch,
                    at=at,
                    user_id=migration_input.user_id,
                )

        if db.is_transaction:
            await allocate_numbers(db=db)
        else:
            async with db.start_transaction() as dbt:
                await allocate_numbers(db=dbt)

        return result
