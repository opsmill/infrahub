from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.constants import NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.pools.registration import get_branches_with_schema_number_pool
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

    async with service.database.start_session() as dbs:
        schema_number_pools = await NodeManager.query(
            db=dbs, schema=CoreNumberPool, filters={"pool_type__value": NumberPoolType.SCHEMA.value}
        )

    for schema_number_pool in list(schema_number_pools):
        defined_on_branches = get_branches_with_schema_number_pool(
            kind=schema_number_pool.node.value, attribute_name=schema_number_pool.node_attribute.value
        )
        if registry.default_branch in defined_on_branches:
            schema = registry.schema.get(name=schema_number_pool.node.value, branch=registry.default_branch)
            attribute = schema.get_attribute(name=schema_number_pool.node_attribute.value)
            number_pool_updated = False
            if isinstance(attribute.parameters, NumberPoolParameters):
                if schema_number_pool.start_range.value != attribute.parameters.start_range:
                    schema_number_pool.start_range.value = attribute.parameters.start_range
                    number_pool_updated = True
                if schema_number_pool.end_range.value != attribute.parameters.end_range:
                    schema_number_pool.end_range.value = attribute.parameters.end_range
                    number_pool_updated = True

            if number_pool_updated:
                log.info(
                    f"Updating NumberPool={schema_number_pool.id} based on changes in the schema on {registry.default_branch}"
                )
                await schema_number_pool.save(db=service.database)

        elif not defined_on_branches:
            log.info(f"Deleting number pool (id={schema_number_pool.id}) as it is no longer defined in the schema")
            await schema_number_pool.delete(db=service.database)
