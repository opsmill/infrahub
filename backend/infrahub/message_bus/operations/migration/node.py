from infrahub.core.migrations import NodeAttributeAddMigration
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages import MigrationNodeAttributeAddResponse
from infrahub.services import InfrahubServices

log = get_logger()


async def attribute_add(message: messages.MigrationNodeAttributeAdd, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        migration = NodeAttributeAddMigration(node_schema=message.node_schema, attribute_name=message.attribute_name)
        execution_result = await migration.execute(db=db, branch=message.branch)

        if message.reply_requested:
            response = MigrationNodeAttributeAddResponse(data=execution_result.model_dump())
            await service.reply(message=response, initiator=message)
