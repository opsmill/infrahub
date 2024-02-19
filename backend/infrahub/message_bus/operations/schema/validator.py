from infrahub.core.validators.aggregated_checker import AggregatedConstraintChecker
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.dependencies.registry import get_component_registry
from infrahub.log import get_logger
from infrahub.message_bus.messages.schema_validator_path import (
    SchemaValidatorPath,
    SchemaValidatorPathResponse,
    SchemaValidatorPathResponseData,
)
from infrahub.services import InfrahubServices

log = get_logger()


async def path(message: SchemaValidatorPath, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        log.info(
            "schema.validator.path",
            constraint=message.constraint_name,
            node_kind=message.node_schema.kind,
            path=message.schema_path.get_path(),
        )

        constraint_request = SchemaConstraintValidatorRequest(
            branch=message.branch,
            constraint_name=message.constraint_name,
            node_schema=message.node_schema,
            schema_path=message.schema_path,
        )

        component_registry = get_component_registry()
        aggregated_constraint_checker = await component_registry.get_component(
            AggregatedConstraintChecker, db=db, branch=message.branch
        )
        violations = await aggregated_constraint_checker.run_constraints(constraint_request)

        if message.reply_requested:
            response = SchemaValidatorPathResponse(
                data=SchemaValidatorPathResponseData(
                    violations=violations, constraint_name=message.constraint_name, schema_path=message.schema_path
                )
            )
            await service.reply(message=response, initiator=message)
