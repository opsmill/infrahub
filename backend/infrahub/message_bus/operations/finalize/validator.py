from infrahub_sdk.protocols import (
    CoreArtifactValidator,
    CoreDataValidator,
    CoreGeneratorValidator,
    CoreRepositoryValidator,
    CoreSchemaValidator,
    CoreUserValidator,
    CoreValidator,
)
from prefect import flow

from infrahub import config
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.types import KVTTL, MessageTTL
from infrahub.services import InfrahubServices
from infrahub.validators.events import send_failed_validator, send_passed_validator

log = get_logger()


@flow(name="validator-finalize-execution")
async def execution(message: messages.FinalizeValidatorExecution, service: InfrahubServices) -> None:
    """Monitors the status of checks associated with a validator and finalizes the conclusion of the validator

    Based on the unique execution_id this function looks expects to see an entry in the cache for each check
    associated with this validator. Upon seeing the result of a check the function will exclude it from further
    checks and update the current conclusion of the validator if any of the checks failed.

    The message will get rescheduled until the timeout has exceeded or until all checks are accounted for.
    """
    validator_type = get_validator_type(validator_type=message.validator_type)
    validator = await service.client.get(kind=validator_type, id=message.validator_id)
    checks_key = f"validator_execution_id:{message.validator_execution_id}:checks"
    current_conclusion = validator.conclusion.value
    if validator.state.value != "in_progress":
        validator.state.value = "in_progress"
        validator.started_at.value = Timestamp().to_string()
        validator.completed_at.value = ""
        await validator.save()

    required_checks_data = await service.cache.get(key=checks_key) or ""
    # Remove instances of empty checks
    required_checks = [required_check for required_check in required_checks_data.split(",") if required_check]

    completed_checks_data = await service.cache.list_keys(
        filter_pattern=f"validator_execution_id:{message.validator_execution_id}:check_execution_id:*"
    )
    completed_checks = [check.split(":")[-1] for check in completed_checks_data]

    missing_checks = [check for check in required_checks if check not in completed_checks]
    checks_to_verify = [check for check in completed_checks if check in required_checks]
    failed_check = False

    for check in checks_to_verify:
        conclusion = await service.cache.get(
            f"validator_execution_id:{message.validator_execution_id}:check_execution_id:{check}"
        )
        if conclusion != "success":
            failed_check = True

    conclusion = "failure" if failed_check else "success"
    if failed_check and current_conclusion != "failure":
        validator.conclusion.value = "failure"
        await validator.save()

    if missing_checks:
        remaining_checks = ",".join(missing_checks)
        await service.cache.set(key=checks_key, value=remaining_checks, expires=KVTTL.TWO_HOURS)
        current_time = Timestamp()
        starting_time = Timestamp(message.start_time)
        deadline = starting_time.add_delta(seconds=config.SETTINGS.miscellaneous.maximum_validator_execution_time)
        if current_time < deadline:
            log.debug(
                "Still waiting for checks to complete",
                missing_checks=missing_checks,
                validator_id=message.validator_id,
                validator_execution_id=message.validator_execution_id,
            )
            await service.message_bus.send(message=message, delay=MessageTTL.FIVE)
            return

        log.info(
            "Timeout reached",
            validator_id=message.validator_id,
            validator_execution_id=message.validator_execution_id,
        )
        conclusion = "failure"

    validator.state.value = "completed"
    validator.completed_at.value = Timestamp().to_string()
    validator.conclusion.value = conclusion
    await validator.save()
    if validator.conclusion.value == ValidatorConclusion.SUCCESS.value:
        await send_passed_validator(
            service=service, validator=validator, proposed_change_id=message.proposed_change, context=message.context
        )
    else:
        await send_failed_validator(
            service=service, validator=validator, proposed_change_id=message.proposed_change, context=message.context
        )


def get_validator_type(
    validator_type: str,
) -> (
    type[CoreArtifactValidator]
    | type[CoreDataValidator]
    | type[CoreGeneratorValidator]
    | type[CoreRepositoryValidator]
    | type[CoreSchemaValidator]
    | type[CoreUserValidator]
    | type[CoreValidator]
):
    match validator_type:
        case InfrahubKind.USERVALIDATOR:
            validator_kind = CoreUserValidator
        case InfrahubKind.SCHEMAVALIDATOR:
            validator_kind = CoreSchemaValidator
        case InfrahubKind.GENERATORVALIDATOR:
            validator_kind = CoreGeneratorValidator
        case InfrahubKind.REPOSITORYVALIDATOR:
            validator_kind = CoreRepositoryValidator
        case InfrahubKind.DATAVALIDATOR:
            validator_kind = CoreDataValidator
        case InfrahubKind.ARTIFACTVALIDATOR:
            validator_kind = CoreArtifactValidator
        case _:
            validator_kind = CoreValidator

    return validator_kind
