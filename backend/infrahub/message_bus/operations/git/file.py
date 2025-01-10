from infrahub.exceptions import FileOutOfRepositoryError, RepositoryFileNotFoundError
from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_file_get import (
    GitFileGetResponse,
    GitFileGetResponseData,
)
from infrahub.services import InfrahubServices

log = get_logger()


async def get(message: messages.GitFileGet, service: InfrahubServices) -> None:
    log.info("Collecting file from repository", repository=message.repository_name, file=message.file)

    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
        commit=message.commit,
    )

    try:
        content = await repo.get_file(commit=message.commit, location=message.file)
    except (FileOutOfRepositoryError, RepositoryFileNotFoundError) as e:
        if message.reply_requested:
            response = GitFileGetResponse(data=GitFileGetResponseData(error_message=e.message, http_code=e.HTTP_CODE))
            await service.message_bus.reply_if_initiator_meta(message=response, initiator=message)
    else:
        if message.reply_requested:
            response = GitFileGetResponse(data=GitFileGetResponseData(content=content))
            await service.message_bus.reply_if_initiator_meta(message=response, initiator=message)
