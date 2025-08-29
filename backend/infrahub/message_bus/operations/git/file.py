from infrahub.exceptions import FileOutOfRepositoryError, RepositoryFileNotFoundError
from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_file_get import (
    GitFileGetResponse,
    GitFileGetResponseData,
)
from infrahub.workers.dependencies import get_client, get_message_bus

log = get_logger()


async def get(message: messages.GitFileGet) -> None:
    log.info("Collecting file from repository", repository=message.repository_name, file=message.file)

    repo = await get_initialized_repo(
        client=get_client(),
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
        commit=message.commit,
    )

    message_bus = await get_message_bus()
    try:
        content = await repo.get_file(commit=message.commit, location=message.file)
    except (FileOutOfRepositoryError, RepositoryFileNotFoundError) as e:
        if message.reply_requested:
            response = GitFileGetResponse(data=GitFileGetResponseData(error_message=e.message, http_code=e.HTTP_CODE))
            await message_bus.reply_if_initiator_meta(message=response, initiator=message)
    else:
        if message.reply_requested:
            response = GitFileGetResponse(data=GitFileGetResponseData(content=content))
            await message_bus.reply_if_initiator_meta(message=response, initiator=message)
