from infrahub import WORKER_IDENTITY
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.registry import refresh_branches

log = get_logger()


async def branches(message: messages.RefreshRegistryBranches, service: InfrahubServices) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring refresh registry refresh request originating from self", worker=WORKER_IDENTITY)
        return

    async with service.database.session as session:
        await refresh_branches(session=session)
