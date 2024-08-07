from __future__ import annotations

from typing import Any, Sequence

from ..query import AttributeMigrationQuery
from ..query.attribute_add import AttributeAddQuery
from ..shared import AttributeSchemaMigration


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
