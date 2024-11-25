from prefect import flow

from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import WEBHOOK_CONFIGURE


@flow(name="event-worker-newprimary-api")
async def new_primary_api(message: messages.EventWorkerNewPrimaryAPI, service: InfrahubServices) -> None:
    service.log.info("api_worker promoted to primary", worker_id=message.worker_id)

    await service.workflow.submit_workflow(workflow=WEBHOOK_CONFIGURE)
