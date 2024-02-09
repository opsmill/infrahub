from infrahub.core.validators.attribute.regex import AttributeRegexUpdateValidator
from infrahub.log import get_logger
from infrahub.message_bus.messages.validator_attribute_regex_update import (
    ValidatorAttributeRegexUpdate,
    ValidatorAttributeRegexUpdateResponse,
    ValidatorAttributeRegexUpdateResponseData,
)
from infrahub.services import InfrahubServices

log = get_logger()


async def regex_update(message: ValidatorAttributeRegexUpdate, service: InfrahubServices) -> None:
    async with service.database.start_session() as db:
        log.info("In regex_update")
        validator = AttributeRegexUpdateValidator(
            node_schema=message.node_schema, attribute_name=message.attribute_name
        )
        violations = await validator.run_validate(db=db, branch=message.branch)

        if message.reply_requested:
            response = ValidatorAttributeRegexUpdateResponse(
                data=ValidatorAttributeRegexUpdateResponseData(violations=violations)
            )
            await service.reply(message=response, initiator=message)
