from infrahub import config
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices

log = get_logger()


async def execution(message: messages.FinalizeValidatorExecution, service: InfrahubServices) -> None:
    """Monitors the status of checks associated with a validator and finalizes the conclusion of the validator

    Based on the unique execution_id this function looks expects to see an entry in the cache for each check
    associated with this validator. Upon seeing the result of a check the function will exclude it from further
    checks and update the current conclusion of the validator if any of the checks failed.

    The message will get rescheduled until the timeout has exceeded or until all checks are accounted for.
    """
    validator = await service.client.get(kind=message.validator_type, id=message.validator_id)
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
        await service.cache.set(key=checks_key, value=remaining_checks, expires=7200)
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
            await service.send(message=message, delay=MessageTTL.FIVE)
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
