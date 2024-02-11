from infrahub.core.migrations import MIGRATION_MAP
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def attribute(message: messages.SchemaMigrationAttribute, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        migration_class = MIGRATION_MAP.get(message.migration_name)
        migration = migration_class(node_schema=message.node_schema, attribute_name=message.attribute_name)
        execution_result = await migration.execute(db=db, branch=message.branch)

        if message.reply_requested:
            response = messages.SchemaMigrationAttributeResponse(data=execution_result.model_dump())
            await service.reply(message=response, initiator=message)


async def relationship(message: messages.SchemaMigrationRelationship, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        migration_class = MIGRATION_MAP.get(message.migration_name)
        migration = migration_class(node_schema=message.node_schema, relationship_name=message.relationship_name)
        execution_result = await migration.execute(db=db, branch=message.branch)

        if message.reply_requested:
            response = messages.SchemaMigrationRelationshipResponse(data=execution_result.model_dump())
            await service.reply(message=response, initiator=message)
