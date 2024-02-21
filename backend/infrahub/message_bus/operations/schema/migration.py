from infrahub.core.migrations import MIGRATION_MAP
from infrahub.log import get_logger
from infrahub.message_bus.messages.schema_migration_path import (
    SchemaMigrationPath,
    SchemaMigrationPathResponse,
    SchemaMigrationPathResponseData,
)
from infrahub.services import InfrahubServices

log = get_logger()


async def path(message: SchemaMigrationPath, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        service.log.info(
            "schema.migration.path",
            migration=message.migration_name,
            node_kind=message.new_node_schema.kind,
            path=message.schema_path.get_path(),
        )
        migration_class = MIGRATION_MAP.get(message.migration_name)
        migration = migration_class(
            new_node_schema=message.new_node_schema,
            previous_node_schema=message.previous_node_schema,
            schema_path=message.schema_path,
        )
        execution_result = await migration.execute(db=db, branch=message.branch)

        if message.reply_requested:
            response = SchemaMigrationPathResponse(data=SchemaMigrationPathResponseData(errors=execution_result.errors))
            await service.reply(message=response, initiator=message)
