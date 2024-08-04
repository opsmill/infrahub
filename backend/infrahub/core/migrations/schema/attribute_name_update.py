from __future__ import annotations

from typing import Any, Sequence

from ..query import AttributeMigrationQuery
from ..query.attribute_rename import AttributeInfo, AttributeRenameQuery
from ..shared import AttributeSchemaMigration


class AttributeNameUpdateMigrationQuery01(AttributeMigrationQuery, AttributeRenameQuery):
    name = "migration_attribute_name_update_01"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ):
        new_attr = AttributeInfo(
            name=migration.new_attribute_schema.name,
            node_kind=migration.new_schema.kind,
            branch_support=migration.new_attribute_schema.get_branch().value,
        )

        attr_id = migration.new_attribute_schema.id
        if not attr_id:
            raise ValueError("The Id is not defined on new_attribute_schema")
        prev_attr_schema = migration.previous_schema.get_attribute_by_id(id=attr_id)

        previous_attr = AttributeInfo(
            name=prev_attr_schema.name,
            node_kind=migration.previous_schema.kind,
            branch_support=prev_attr_schema.get_branch().value,
        )

        super().__init__(migration=migration, new_attr=new_attr, previous_attr=previous_attr, **kwargs)

    def get_nbr_migrations_executed(self) -> int:
        return self.stats.get_counter(name="nodes_created")


class AttributeNameUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.name.update"
    queries: Sequence[type[AttributeMigrationQuery]] = [AttributeNameUpdateMigrationQuery01]  # type: ignore[assignment]
