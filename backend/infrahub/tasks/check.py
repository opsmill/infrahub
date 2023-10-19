from infrahub.log import get_logger
from infrahub.message_bus import InfrahubBaseMessage, Meta
from infrahub.services import InfrahubServices

log = get_logger()


async def set_check_status(message: InfrahubBaseMessage, conclusion: str, service: InfrahubServices) -> None:
    message.meta = message.meta or Meta()
    if message.meta.validator_execution_id and message.meta.check_execution_id:
        key = f"validator_execution_id:{message.meta.validator_execution_id}:check_execution_id:{message.meta.check_execution_id}"
        await service.cache.set(
            key=key,
            value=conclusion,
            expires=7200,
        )
        log.debug("setting check status in cache", key=key, conclusion=conclusion)
