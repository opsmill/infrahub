from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import NodeNotFoundError
from infrahub.pools.models import NumberPoolLockDefinition
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

    existing_pool_ids = [pool.id for pool in schema_number_pools]
    for registry_branch in registry.schema.get_branches():
        schema_branch = service.database.schema.get_schema_branch(name=registry_branch)

        for generic_name in schema_branch.generic_names:
            generic_node = schema_branch.get_generic(name=generic_name, duplicate=False)
            for attribute_name in generic_node.attribute_names:
                attribute = generic_node.get_attribute(name=attribute_name)
                if isinstance(attribute.parameters, NumberPoolParameters) and attribute.parameters.number_pool_id:
                    if attribute.parameters.number_pool_id not in existing_pool_ids:
                        await _create_number_pool(
                            service=service,
                            number_pool_id=attribute.parameters.number_pool_id,
                            pool_node=generic_node.kind,
                            pool_attribute=attribute_name,
                            start_range=attribute.parameters.start_range,
                            end_range=attribute.parameters.end_range,
                        )
                        existing_pool_ids.append(attribute.parameters.number_pool_id)

        for node_name in schema_branch.node_names:
            node = schema_branch.get_node(name=node_name, duplicate=False)
            for attribute_name in node.attribute_names:
                attribute = node.get_attribute(name=attribute_name)
                if isinstance(attribute.parameters, NumberPoolParameters) and attribute.parameters.number_pool_id:
                    if attribute.parameters.number_pool_id not in existing_pool_ids:
                        await _create_number_pool(
                            service=service,
                            number_pool_id=attribute.parameters.number_pool_id,
                            pool_node=node.kind,
                            pool_attribute=attribute_name,
                            start_range=attribute.parameters.start_range,
                            end_range=attribute.parameters.end_range,
                        )
                        existing_pool_ids.append(attribute.parameters.number_pool_id)


async def _create_number_pool(
    service: InfrahubServices,
    number_pool_id: str,
    pool_node: str,
    pool_attribute: str,
    start_range: int,
    end_range: int,
) -> None:
    lock_definition = NumberPoolLockDefinition(pool_id=number_pool_id)
    async with lock.registry.get(name=lock_definition.lock_name, namespace=lock_definition.namespace_name, local=False):
        async with service.database.start_session() as dbs:
            try:
                await registry.manager.get_one_by_id_or_default_filter(
                    db=dbs, id=str(number_pool_id), kind=CoreNumberPool
                )
            except NodeNotFoundError:
                number_pool = await Node.init(db=dbs, schema=InfrahubKind.NUMBERPOOL, branch=registry.default_branch)
                await number_pool.new(
                    db=dbs,
                    id=number_pool_id,
                    name=f"{pool_node}.{pool_attribute} [{number_pool_id}]",
                    node=pool_node,
                    node_attribute=pool_attribute,
                    start_range=start_range,
                    end_range=end_range,
                    pool_type=NumberPoolType.SCHEMA.value,
                )
                await number_pool.save(db=dbs)
