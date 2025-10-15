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
            attribute_name=migration.previous_attribute_schema.name,
            node_kinds=[migration.new_schema.kind],
            **kwargs,
        )


class NodeAttributeRemoveMigration(AttributeSchemaMigration):
    name: str = "node.attribute.remove"
    queries: Sequence[type[AttributeMigrationQuery]] = [NodeAttributeRemoveMigrationQuery01]  # type: ignore[assignment]
