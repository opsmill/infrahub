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


class Migration007(InternalSchemaMigration):
    name: str = "007_add_allow_override"
    minimum_version: int = 6

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        internal_schema = cls.get_internal_schema()
        schema_rel = internal_schema.get_node(name="SchemaRelationship")
        schema_attr = internal_schema.get_node(name="SchemaAttribute")

        migrations = [
            NodeAttributeAddMigration(
                new_node_schema=schema_attr,
                previous_node_schema=schema_attr,
                schema_path=SchemaPath(
                    schema_kind="SchemaAttribute", path_type=SchemaPathType.ATTRIBUTE, field_name="allow_override"
                ),
            ),
            NodeAttributeAddMigration(
                new_node_schema=schema_rel,
                previous_node_schema=schema_rel,
                schema_path=SchemaPath(
                    schema_kind="SchemaRelationship", path_type=SchemaPathType.ATTRIBUTE, field_name="allow_override"
                ),
            ),
        ]
        return cls(migrations=migrations, **kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
