from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List, Optional

from infrahub.message_bus.messages.schema_migration_path import SchemaMigrationPath, SchemaMigrationPathResponse

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema_manager import SchemaBranch
    from infrahub.services import InfrahubServices


async def schema_migrations_runner(
    branch: Branch,
    new_schema: SchemaBranch,
    previous_schema: SchemaBranch,
    migrations: List[SchemaUpdateMigrationInfo],
    service: InfrahubServices,
) -> List[str]:
    tasks = []
    error_messages: List[str] = []

    if not migrations:
        return error_messages

    for migration in migrations:
        service.log.info(
            f"Preparing migration for {migration.migration_name!r} ({migration.routing_key})", branch=branch.name
        )

        new_node_schema: Optional[MainSchemaTypes] = None
        previous_node_schema: Optional[MainSchemaTypes] = None

        if new_schema.has(name=migration.path.schema_kind):
            new_node_schema = new_schema.get(name=migration.path.schema_kind)

        if new_node_schema and new_node_schema.id:
            previous_node_schema = previous_schema.get_by_id(id=new_node_schema.id)
        else:
            previous_node_schema = previous_schema.get(name=migration.path.schema_kind)

        if not previous_node_schema:
            raise ValueError(
                f"Unable to find the previous version of the schema for {migration.path.schema_kind}, in order to run the migration."
            )

        message = SchemaMigrationPath(
            branch=branch,
            migration_name=migration.migration_name,
            new_node_schema=new_node_schema,
            previous_node_schema=previous_node_schema,
            schema_path=migration.path,
        )
        tasks.append(service.message_bus.rpc(message=message, response_class=SchemaMigrationPathResponse))

    responses: list[SchemaMigrationPathResponse] = await asyncio.gather(*tasks)  # type: ignore[assignment]

    for response in responses:
        error_messages.extend(response.data.errors)

    return error_messages
