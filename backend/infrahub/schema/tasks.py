from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.pools.tasks import validate_schema_number_pools
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.workflows.utils import wait_for_schema_to_converge


@flow(
    name="schema-updated",
    flow_run_name="Running actions after the schema was updated on '{branch_name}'",
)
async def schema_updated(
    branch_name: str,
    schema_hash: str,  # noqa: ARG001
    context: InfrahubContext,
    service: InfrahubServices,
) -> None:
    log = get_run_logger()
    await wait_for_schema_to_converge(
        branch_name=branch_name, component=service.component, db=service.database, log=log
    )

    await validate_schema_number_pools(branch_name=branch_name, context=context, service=service)
