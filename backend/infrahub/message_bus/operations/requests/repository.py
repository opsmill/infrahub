from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def check(message: messages.RequestRepositoryChecks, service: InfrahubServices):
    repository = await service.client.get(kind="CoreRepository", id=message.repository, branch=message.branch)
    log.info(f"Got a request to process checks defined in repository: {repository.id}")
