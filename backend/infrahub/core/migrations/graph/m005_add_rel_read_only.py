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


class Migration005(InternalSchemaMigration):
    name: str = "005_add_rel_read_only"
    minimum_version: int = 4

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        internal_schema = cls.get_internal_schema()
        schema_rel = internal_schema.get_node(name="SchemaRelationship")

        migrations = [
            NodeAttributeAddMigration(
                new_node_schema=schema_rel,
                previous_node_schema=schema_rel,
                schema_path=SchemaPath(
                    schema_kind="SchemaRelationship", path_type=SchemaPathType.ATTRIBUTE, field_name="read_only"
                ),
            ),
        ]
        return cls(migrations=migrations, **kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
