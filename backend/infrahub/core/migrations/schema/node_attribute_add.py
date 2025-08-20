from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.exceptions import PoolExhaustedError
from infrahub.tasks.registry import update_branch_registry

from ..query import AttributeMigrationQuery
from ..query.attribute_add import AttributeAddQuery
from ..shared import AttributeSchemaMigration, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase

    from ...branch import Branch
    from ...timestamp import Timestamp


class NodeAttributeAddMigrationQuery01(AttributeMigrationQuery, AttributeAddQuery):
    name = "migration_node_attribute_add_01"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ):
        super().__init__(
            migration=migration,
            node_kind=migration.new_schema.kind,
            attribute_name=migration.new_attribute_schema.name,
            attribute_kind=migration.new_attribute_schema.kind,
            branch_support=migration.new_attribute_schema.get_branch().value,
            default_value=migration.new_attribute_schema.default_value,
            **kwargs,
        )


class NodeAttributeAddMigration(AttributeSchemaMigration):
    name: str = "node.attribute.add"
    queries: Sequence[type[AttributeMigrationQuery]] = [NodeAttributeAddMigrationQuery01]  # type: ignore[assignment]

    async def execute_post_queries(
        self,
        db: InfrahubDatabase,
        result: MigrationResult,
        branch: Branch,
        at: Timestamp,  # noqa: ARG002
    ) -> MigrationResult:
        if self.new_attribute_schema.kind != "NumberPool":
            return result

        number_pool: CoreNumberPool = await Node.fetch_or_create_number_pool(  # type: ignore[assignment]
            db=db, branch=branch, schema_node=self.new_schema, schema_attribute=self.new_attribute_schema
        )

        await update_branch_registry(db=db, branch=branch)

        nodes: list[Node] = await registry.manager.query(
            db=db, branch=branch, schema=self.new_schema, fields={"id": True, self.new_attribute_schema.name: True}
        )

        try:
            numbers = await number_pool.get_next_many(
                db=db,
                branch=branch,
                quantity=len(nodes),
                attribute=self.new_attribute_schema,
            )
        except PoolExhaustedError as exc:
            result.errors.append(str(exc))
            return result

        for node, number in zip(nodes, numbers, strict=True):
            await number_pool.reserve(db=db, number=number, identifier=node.get_id())
            attr = getattr(node, self.new_attribute_schema.name)
            attr.value = number
            attr.source = number_pool.id

            await node.save(db=db, fields=[self.new_attribute_schema.name])

        return result
