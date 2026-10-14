from infrahub.git.state.commit_log_wire import message_to_request, result_to_response_data
from infrahub.git.state.log_reader import RepositoryLogReader
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_commit_log_get import GitCommitLogGetResponse
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_cache, get_message_bus, get_workflow

log = get_logger()


async def get(message: messages.GitCommitLogGet) -> None:
    log.info("Reading commit log from repository", repository=message.repository_name, git_ref=message.git_ref)

    reader = RepositoryLogReader(cache=await get_cache(), workflow=get_workflow(), worker_identity=WORKER_IDENTITY)
    try:
        result = await reader.commits(request=message_to_request(message=message))
    # The failure reaches the caller as a reply carrying only its message, so the traceback is kept here.
    except Exception:
        log.exception("Reading the commit log failed", repository=message.repository_name, git_ref=message.git_ref)
        raise

    if not message.reply_requested:
        return

    message_bus = await get_message_bus()
    await message_bus.reply_if_initiator_meta(
        message=GitCommitLogGetResponse(data=result_to_response_data(result=result)),
        initiator=message,
    )
