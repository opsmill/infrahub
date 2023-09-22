from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubResponse, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def get(message: messages.GitFileGet, service: InfrahubServices) -> None:
    log.info("Collecting file from repository", repository=message.repository_name, file=message.file)
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=service.client)

    content = await repo.get_file(commit=message.commit, location=message.file)

    if message.reply_requested:
        response = InfrahubResponse(response_class="content_response", response_data={"content": content})
        await service.reply(message=response, initiator=message)
