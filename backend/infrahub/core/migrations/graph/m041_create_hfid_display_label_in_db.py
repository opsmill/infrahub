from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.path import SchemaPath

from ..schema.node_attribute_add import NodeAttributeAddMigration
from ..shared import InternalSchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration041(InternalSchemaMigration):
    name: str = "041_create_hfid_display_label_in_db"
    minimum_version: int = 39  # Will switch to 40 later

    @classmethod
    def init(cls, **kwargs: Any) -> Self:
        internal_schema = cls.get_internal_schema()
        schema_node = internal_schema.get_node(name="SchemaNode")

        migrations = [
            NodeAttributeAddMigration(
                new_node_schema=schema_node,
                previous_node_schema=schema_node,
                schema_path=SchemaPath(
                    schema_kind="SchemaNode", path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                ),
            ),
            # NOTE: This already exists, introduced by Migration008
            # NodeAttributeAddMigration(
            #     new_node_schema=schema_node,
            #     previous_node_schema=schema_node,
            #     schema_path=SchemaPath(
            #         schema_kind="SchemaNode", path_type=SchemaPathType.ATTRIBUTE, field_name="human_friendly_id"
            #     ),
            # ),
        ]
        return cls(migrations=migrations, **kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
