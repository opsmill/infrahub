from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.branch.models import Branch
from infrahub.core.registry import registry
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow


@flow(
    name="validate-schema-number-pools",
    flow_run_name="Validate schema number pools",
)
async def validate_schema_number_pools(
    branch_name: str,  # noqa: ARG001
    context: InfrahubContext,
    service: InfrahubServices,
) -> set[str]:
    log = get_run_logger()
    synchronizer = SchemaNumberPoolSynchronizer(
        db=service.database,
        schema_manager=registry.schema,
        upserter=SchemaNumberPoolUpserter(db=service.database, schema_manager=registry.schema),
        log=log,
    )
    updated_branches = await synchronizer.run(user_id=context.account.account_id)

    if updated_branches:
        for updated_branch_name in updated_branches:
            branch = await Branch.get_by_name(db=service.database, name=updated_branch_name)
            branch.update_schema_hash()
            await branch.save(db=service.database, user_id=context.account.account_id)
            log.info(f"Updated schema hash for branch {updated_branch_name} after number pool synchronization")

        await service.component.refresh_schema_hash(branches=list(updated_branches))
        await service.message_bus.send(RefreshRegistryBranches())

    return updated_branches
