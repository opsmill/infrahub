from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.registry import registry
from infrahub.pools.tasks import validate_schema_number_pools
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.workflows.utils import wait_for_schema_to_converge


@flow(
    name="branch-merged",
    flow_run_name="Running actions after '{source_branch}' was merged",
)
async def branch_merged(
    source_branch: str,  # noqa: ARG001
    context: InfrahubContext,
    service: InfrahubServices,
    target_branch: str | None = None,
) -> None:
    target_branch = target_branch or registry.default_branch
    log = get_run_logger()
    await wait_for_schema_to_converge(
        branch_name=target_branch, component=service.component, db=service.database, log=log
    )

    await validate_schema_number_pools(branch_name=target_branch, context=context, service=service)
