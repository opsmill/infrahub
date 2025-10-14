from __future__ import annotations

from typing import Any, Sequence

from ..query import AttributeMigrationQuery
from ..query.attribute_remove import AttributeRemoveQuery
from ..shared import AttributeSchemaMigration


class NodeAttributeRemoveMigrationQuery01(AttributeMigrationQuery, AttributeRemoveQuery):
    name = "migration_node_attribute_remove_01"
    insert_return: bool = False

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ):
        super().__init__(
            migration=migration,
            attribute_name=migration.new_attribute_schema.name,
            new_node_schema=migration.new_schema,
            branch_support=migration.new_attribute_schema.get_branch().value,
            **kwargs,
        )


class NodeAttributeRemoveMigration(AttributeSchemaMigration):
    name: str = "node.attribute.remove"
    queries: Sequence[type[AttributeMigrationQuery]] = [NodeAttributeRemoveMigrationQuery01]  # type: ignore[assignment]
