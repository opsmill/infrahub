from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def new_primary_api(message: messages.EventWorkerNewPrimaryAPI, service: InfrahubServices) -> None:
    service.log.info("api_worker promoted to primary", worker_id=message.worker_id)

    msg = messages.RefreshWebhookConfiguration()

    msg.assign_meta(parent=message)
    await service.send(message=msg)
