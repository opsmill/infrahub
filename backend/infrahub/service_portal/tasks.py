from __future__ import annotations

from prefect import flow, get_run_logger

from infrahub.auth.session import AccountSession
from infrahub.context import InfrahubContext
from infrahub.service_portal.fulfilment import ServiceRequestRunner, ServiceRequestStateWriter
from infrahub.service_portal.models import ServiceRequestRun  # noqa: TC001 needed for prefect flow
from infrahub.workers.dependencies import get_client, get_database, get_event_service, get_workflow
from infrahub.workflows.utils import add_tags

WORKER_ACCOUNT = "query { AccountProfile { id } }"


@flow(name="service-request-run", flow_run_name="Fulfil service request {model.request_id}")
async def run_service_request(model: ServiceRequestRun, context: InfrahubContext) -> None:
    # STUB(Phase 2): any exception fails the task and leaves the request in `generating`.
    await add_tags(nodes=[model.request_id])

    database = await get_database()
    client = get_client().clone()
    worker_account_id = (await client.execute_graphql(query=WORKER_ACCOUNT))["AccountProfile"]["id"]
    worker_context = InfrahubContext(
        branch=context.branch, account=AccountSession(account_id=worker_account_id, auth_type=context.account.auth_type)
    )
    runner = ServiceRequestRunner(
        database=database,
        workflow=get_workflow(),
        client=client,
        state=ServiceRequestStateWriter(
            database=database, event_service=await get_event_service(), context=worker_context
        ),
        worker_context=worker_context,
    )

    proposed_change_id = await runner.run(request_id=model.request_id, context=context)
    get_run_logger().info(f"Service request {model.request_id} is in review with proposed change {proposed_change_id}")
