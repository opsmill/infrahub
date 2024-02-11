from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List

from infrahub.message_bus.messages import MESSAGE_MAP, RESPONSE_MAP

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema_manager import SchemaBranch, SchemaUpdateMigrationInfo
    from infrahub.message_bus.messages.schema_migration_path import SchemaMigrationPathResponse
    from infrahub.services import InfrahubServices


async def schema_migrations_runner(
    branch: Branch, schema: SchemaBranch, migrations: List[SchemaUpdateMigrationInfo], service: InfrahubServices
) -> List[str]:
    tasks = []
    error_messages: List[str] = []

    if not migrations:
        return error_messages

    for migration in migrations:
        service.log.info(
            f"Preparing migration for {migration.migration_name!r} ({migration.routing_key})", branch=branch.name
        )
        message_class = MESSAGE_MAP.get(migration.routing_key, None)
        response_class = RESPONSE_MAP.get(migration.routing_key, None)

        if not message_class:
            raise ValueError(f"Unable to find the message for {migration.migration_name!r} ({migration.routing_key})")
        if not response_class:
            raise ValueError(f"Unable to find the response for {migration.migration_name!r} ({migration.routing_key})")

        message = message_class(  # type: ignore[call-arg]
            branch=branch,
            migration_name=migration.migration_name,
            node_schema=schema.get(name=migration.path.schema_kind),
            schema_path=migration.path,
        )
        tasks.append(service.message_bus.rpc(message=message, response_class=response_class))

    responses: list[SchemaMigrationPathResponse] = await asyncio.gather(*tasks)  # type: ignore[assignment]

    for response in responses:
        error_messages.extend(response.data.errors)

    return error_messages
