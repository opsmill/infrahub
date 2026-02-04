from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.registry import registry
from infrahub.pools.synchronizer import SchemaNumberPoolSynchronizer
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow


@flow(
    name="validate-schema-number-pools",
    flow_run_name="Validate schema number pools on {branch_name}",
)
async def validate_schema_number_pools(
    branch_name: str,  # noqa: ARG001
    context: InfrahubContext,  # noqa: ARG001
    service: InfrahubServices,
) -> None:
    log = get_run_logger()
    synchronizer = SchemaNumberPoolSynchronizer(
        db=service.database,
        log=log,
        schema_manager=registry.schema,
    )
    await synchronizer.run()
