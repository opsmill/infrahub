from prefect import flow

from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


@flow(name="event-schema-update")
async def update(message: messages.EventSchemaUpdate, service: InfrahubServices) -> None:
    log.info("run_message", branch=message.branch)

    msg = messages.RefreshRegistryBranches()

    msg.assign_meta(parent=message)
    await service.send(message=msg)
