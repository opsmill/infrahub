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


class Migration006(InternalSchemaMigration):
    name: str = "006_add_rel_on_delete"
    minimum_version: int = 5

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        internal_schema = cls.get_internal_schema()
        schema_rel = internal_schema.get_node(name="SchemaRelationship")

        migrations = [
            NodeAttributeAddMigration(
                new_node_schema=schema_rel,
                previous_node_schema=schema_rel,
                schema_path=SchemaPath(
                    schema_kind="SchemaRelationship", path_type=SchemaPathType.ATTRIBUTE, field_name="on_delete"
                ),
            ),
        ]
        return cls(migrations=migrations, **kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
