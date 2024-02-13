from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
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
        validator_class = CONSTRAINT_VALIDATOR_MAP.get(message.constraint_name)
        validator = validator_class(node_schema=message.node_schema, schema_path=message.schema_path)
        violations = await validator.run_validate(db=db, branch=message.branch)

        if message.reply_requested:
            response = SchemaValidatorPathResponse(
                data=SchemaValidatorPathResponseData(
                    violations=violations, constraint_name=message.constraint_name, schema_path=message.schema_path
                )
            )
            await service.reply(message=response, initiator=message)
