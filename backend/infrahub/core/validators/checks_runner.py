import asyncio
from typing import Any, Coroutine

from infrahub_sdk.protocols import CoreValidator

from infrahub.context import InfrahubContext
from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.services import InfrahubServices
from infrahub.validators.events import send_failed_validator, send_passed_validator


async def run_checks_and_update_validator(
    checks: list[Coroutine[Any, None, ValidatorConclusion]],
    validator: CoreValidator,
    context: InfrahubContext,
    service: InfrahubServices,
    proposed_change_id: str,
) -> None:
    """
    Execute a list of checks coroutines, and set validator fields accordingly.
    Tasks are retrieved by completion order so as soon as we detect a failing check,
    we set validator conclusion to failure.
    """

    # First set validator to in progress, then wait for results
    validator.state.value = ValidatorState.IN_PROGRESS.value
    validator.started_at.value = Timestamp().to_string()
    validator.completed_at.value = ""
    await validator.save()

    failed_early = False

    for earliest_task in asyncio.as_completed(checks):
        result = await earliest_task
        if validator.conclusion.value != ValidatorConclusion.FAILURE.value and result == ValidatorConclusion.FAILURE:
            validator.conclusion.value = ValidatorConclusion.FAILURE.value
            failed_early = True
            await validator.save()
            await send_failed_validator(
                service=service, validator=validator, proposed_change_id=proposed_change_id, context=context
            )
            # Continue to iterate to wait for the end of all checks

    validator.state.value = ValidatorState.COMPLETED.value
    validator.completed_at.value = Timestamp().to_string()
    if validator.conclusion.value != ValidatorConclusion.FAILURE.value:
        validator.conclusion.value = ValidatorConclusion.SUCCESS.value

    await validator.save()

    if not failed_early:
        if validator.conclusion.value == ValidatorConclusion.SUCCESS.value:
            await send_passed_validator(
                service=service, validator=validator, proposed_change_id=proposed_change_id, context=context
            )
        else:
            await send_failed_validator(
                service=service, validator=validator, proposed_change_id=proposed_change_id, context=context
            )
