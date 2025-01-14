from __future__ import annotations

from infrahub_sdk.batch import InfrahubBatch
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.path import SchemaPath  # noqa: TC001
from infrahub.core.schema import GenericSchema, NodeSchema  # noqa: TC001
from infrahub.core.validators.aggregated_checker import AggregatedConstraintChecker
from infrahub.core.validators.model import (
    SchemaConstraintValidatorRequest,
)
from infrahub.dependencies.registry import get_component_registry
from infrahub.services import services
from infrahub.workflows.utils import add_tags

from .models.validate_migration import SchemaValidateMigrationData, SchemaValidatorPathResponseData


@flow(name="schema_validate_migrations", flow_run_name="Validate schema migrations", persist_result=True)
async def schema_validate_migrations(message: SchemaValidateMigrationData) -> list[SchemaValidatorPathResponseData]:
    batch = InfrahubBatch(return_exceptions=True)
    log = get_run_logger()
    await add_tags(branches=[message.branch.name])

    if not message.constraints:
        log.info("No constaint to validate")
        return []

    log.info(f"{len(message.constraints)} constraint(s) to validate")
    # NOTE this task is a good candidate to add a progress bar
    for constraint in message.constraints:
        schema = message.schema_branch.get(name=constraint.path.schema_kind)
        if not isinstance(schema, (GenericSchema, NodeSchema)):
            continue
        batch.add(
            task=schema_path_validate,
            branch=message.branch,
            constraint_name=constraint.constraint_name,
            node_schema=schema,
            schema_path=constraint.path,
        )

    results = [result async for _, result in batch.execute()]
    return results


@task(
    name="schema-path-validate",
    task_run_name="Validate schema path {constraint_name} in {branch.name}",
    description="Validate if a given migration is compatible with the existing data",
    retries=3,
    cache_policy=NONE,
)
async def schema_path_validate(
    branch: Branch,
    constraint_name: str,
    node_schema: NodeSchema | GenericSchema,
    schema_path: SchemaPath,
) -> SchemaValidatorPathResponseData:
    service = services.service

    async with service.database.start_session() as db:
        constraint_request = SchemaConstraintValidatorRequest(
            branch=branch,
            constraint_name=constraint_name,
            node_schema=node_schema,
            schema_path=schema_path,
        )

        component_registry = get_component_registry()
        aggregated_constraint_checker = await component_registry.get_component(
            AggregatedConstraintChecker, db=db, branch=branch
        )
        violations = await aggregated_constraint_checker.run_constraints(constraint_request)

        return SchemaValidatorPathResponseData(
            violations=violations, constraint_name=constraint_name, schema_path=schema_path
        )
