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


class Migration004(InternalSchemaMigration):
    name: str = "004_node_add_attr_documentation"
    minimum_version: int = 3

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        internal_schema = cls.get_internal_schema()
        schema_node = internal_schema.get_node(name="SchemaNode")
        schema_generic = internal_schema.get_node(name="SchemaGeneric")

        migrations = [
            NodeAttributeAddMigration(
                new_node_schema=schema_node,
                previous_node_schema=schema_node,
                schema_path=SchemaPath(
                    schema_kind="SchemaNode", path_type=SchemaPathType.ATTRIBUTE, field_name="documentation"
                ),
            ),
            NodeAttributeAddMigration(
                new_node_schema=schema_generic,
                previous_node_schema=schema_generic,
                schema_path=SchemaPath(
                    schema_kind="SchemaGeneric", path_type=SchemaPathType.ATTRIBUTE, field_name="documentation"
                ),
            ),
        ]
        return cls(migrations=migrations, **kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
