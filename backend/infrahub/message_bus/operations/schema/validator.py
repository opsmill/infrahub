from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def attribute(message: messages.SchemaValidatorAttribute, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        log.info(
            "schema.validator.attribute",
            constraint=message.constraint_name,
            node_kind=message.node_schema.kind,
            attribute_name=message.attribute_name,
        )
        validator_class = CONSTRAINT_VALIDATOR_MAP.get(message.constraint_name)
        validator = validator_class(node_schema=message.node_schema, attribute_name=message.attribute_name)
        violations = await validator.run_validate(db=db, branch=message.branch)

        if message.reply_requested:
            response = messages.SchemaValidatorAttributeResponse(data={"violations": violations})
            await service.reply(message=response, initiator=message)
