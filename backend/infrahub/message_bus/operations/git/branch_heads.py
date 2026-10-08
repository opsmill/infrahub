from infrahub.git.state.branch_heads_wire import message_to_request, result_to_response_data
from infrahub.git.state.log_reader import RepositoryLogReader
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_branch_heads_get import GitBranchHeadsGetResponse
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_cache, get_message_bus, get_workflow

log = get_logger()


async def get(message: messages.GitBranchHeadsGet) -> None:
    log.info("Reading branch heads from repository", repository=message.repository_name)

    reader = RepositoryLogReader(cache=await get_cache(), workflow=get_workflow(), worker_identity=WORKER_IDENTITY)
    try:
        result = await reader.branch_heads(request=message_to_request(message=message))
    # The failure reaches the caller as a reply carrying only its message, so the traceback is kept here.
    except Exception:
        log.exception("Reading the branch heads failed", repository=message.repository_name)
        raise

    if not message.reply_requested:
        return

    message_bus = await get_message_bus()
    await message_bus.reply_if_initiator_meta(
        message=GitBranchHeadsGetResponse(data=result_to_response_data(result=result)),
        initiator=message,
    )
