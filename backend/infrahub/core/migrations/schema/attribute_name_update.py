from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING, Any, ClassVar

from infrahub.core.migrations.schema.phases import MigrationPhase

from ..query import AttributeMigrationQuery
from ..query.attribute_rename import AttributeInfo, AttributeRenameQuery
from ..query.owner_set_attribute import OwnerSetKeyMigrationQuery, profile_and_template_kinds
from ..shared import AttributeSchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AttributeNameUpdateMigrationQuery01(AttributeMigrationQuery, AttributeRenameQuery):
    name = "migration_attribute_name_update_01"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        new_attr = AttributeInfo(
            name=migration.new_attribute_schema.name,
            node_kind=migration.new_schema.kind,
            branch_support=migration.new_attribute_schema.get_branch().value,
        )

        # For inherited attributes, id is None but source_attribute_id contains the generic's attribute ID
        attr_id = migration.new_attribute_schema.id or migration.new_attribute_schema.source_attribute_id
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


class AttributeNameUpdateMigrationQuery02(AttributeMigrationQuery, OwnerSetKeyMigrationQuery):
    """Move the owners that profiles and object templates give to the attribute to its new name."""

    name = "migration_attribute_name_update_02"

    def __init__(self, migration: AttributeSchemaMigration, **kwargs: Any) -> None:
        attr_id = migration.new_attribute_schema.id or migration.new_attribute_schema.source_attribute_id
        if not attr_id:
            raise ValueError("The Id is not defined on new_attribute_schema")
        super().__init__(
            migration=migration,
            node_kinds=[],
            set_key={"attribute": migration.previous_schema.get_attribute_by_id(id=attr_id).name},
            new_set_key={"attribute": migration.new_attribute_schema.name},
            **kwargs,
        )

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.node_kinds, self.kinds_to_skip = profile_and_template_kinds(
            db=db,
            branch=self.branch,
            node_kind=self.migration.previous_schema.kind,
            attribute_name=self.set_key["attribute"],
        )
        await super().query_init(db=db, **kwargs)


class AttributeNameUpdateMigration(AttributeSchemaMigration):
    phase: ClassVar[MigrationPhase] = MigrationPhase.ATTRIBUTE_RENAME
    name: str = "attribute.name.update"
    queries: Sequence[type[AttributeMigrationQuery]] = [
        AttributeNameUpdateMigrationQuery01,
        AttributeNameUpdateMigrationQuery02,
    ]
