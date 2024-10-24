from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub_sdk.batch import InfrahubBatch
from prefect import flow

from infrahub.message_bus.messages.schema_migration_path import (
    SchemaMigrationPathData,
)
from infrahub.message_bus.operations.schema.migration import schema_path_migrate
from infrahub.services import services
from infrahub.workflows.utils import add_branch_tag

from .models import SchemaApplyMigrationData  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


@flow(name="schema-migrations-apply")
async def schema_apply_migrations(message: SchemaApplyMigrationData) -> list[str]:
    service = services.service
    await add_branch_tag(branch_name=message.branch.name)

    batch = InfrahubBatch()
    error_messages: list[str] = []

    if not message.migrations:
        return error_messages

    for migration in message.migrations:
        service.log.info(
            f"Preparing migration for {migration.migration_name!r} ({migration.routing_key})",
            branch=message.branch.name,
        )

        new_node_schema: Optional[MainSchemaTypes] = None
        previous_node_schema: Optional[MainSchemaTypes] = None

        if message.new_schema.has(name=migration.path.schema_kind):
            new_node_schema = message.new_schema.get(name=migration.path.schema_kind)

        if new_node_schema and new_node_schema.id:
            previous_node_schema = message.previous_schema.get_by_id(id=new_node_schema.id)
        else:
            previous_node_schema = message.previous_schema.get(name=migration.path.schema_kind)

        if not previous_node_schema:
            raise ValueError(
                f"Unable to find the previous version of the schema for {migration.path.schema_kind}, in order to run the migration."
            )

        msg = SchemaMigrationPathData(
            branch=message.branch,
            migration_name=migration.migration_name,
            new_node_schema=new_node_schema,
            previous_node_schema=previous_node_schema,
            schema_path=migration.path,
        )

        batch.add(task=schema_path_migrate, message=msg)

    async for _, result in batch.execute():
        error_messages.extend(result.errors)

    return error_messages
