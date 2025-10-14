from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.progress import Progress
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import initialization
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.shared import InternalSchemaMigration, MigrationResult
from infrahub.core.path import SchemaPath
from infrahub.lock import initialize_lock

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration041(InternalSchemaMigration):
    name: str = "041_create_hfid_display_label_in_db"
    minimum_version: int = 40

    @classmethod
    def init(cls, **kwargs: Any) -> Self:
        internal_schema = cls.get_internal_schema()
        schema_node = internal_schema.get_node(name="SchemaNode")
        schema_generic = internal_schema.get_node(name="SchemaGeneric")

        cls.migrations = [
            # HFID is not needed, it was introduced at graph v8
            NodeAttributeAddMigration(
                new_node_schema=schema_node,
                previous_node_schema=schema_node,
                schema_path=SchemaPath(
                    schema_kind="SchemaNode", path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                ),
            ),
            NodeAttributeAddMigration(
                new_node_schema=schema_generic,
                previous_node_schema=schema_generic,
                schema_path=SchemaPath(
                    schema_kind="SchemaGeneric", path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                ),
            ),
        ]
        return cls(migrations=cls.migrations, **kwargs)  # type: ignore[arg-type]

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        default_branch = registry.get_branch_from_registry()
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

        migrations = list(self.migrations)

        for node_schema_kind in schema_branch.node_names:
            schema = schema_branch.get(name=node_schema_kind, duplicate=False)
            migrations.extend(
                [
                    NodeAttributeAddMigration(
                        new_node_schema=schema,
                        previous_node_schema=schema,
                        schema_path=SchemaPath(
                            schema_kind=schema.kind, path_type=SchemaPathType.ATTRIBUTE, field_name="human_friendly_id"
                        ),
                    ),
                    NodeAttributeAddMigration(
                        new_node_schema=schema,
                        previous_node_schema=schema,
                        schema_path=SchemaPath(
                            schema_kind=schema.kind, path_type=SchemaPathType.ATTRIBUTE, field_name="display_label"
                        ),
                    ),
                ]
            )

        with Progress() as progress:
            update_task = progress.add_task("Adding HFID and display label to nodes", total=len(migrations))

            for migration in migrations:
                try:
                    execution_result = await migration.execute(db=db, branch=default_branch)
                    result.errors.extend(execution_result.errors)
                    progress.update(update_task, advance=1)
                except Exception as exc:
                    result.errors.append(str(exc))
                    return result

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
