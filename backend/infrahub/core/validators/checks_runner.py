import asyncio
from typing import Any, Coroutine

from infrahub_sdk.node import InfrahubNode

from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp


async def run_checks_and_update_validator(
    checks: list[Coroutine[Any, None, ValidatorConclusion]], validator: InfrahubNode
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

    for earliest_task in asyncio.as_completed(checks):
        result = await earliest_task
        if validator.conclusion.value != ValidatorConclusion.FAILURE.value and result == ValidatorConclusion.FAILURE:
            validator.conclusion.value = ValidatorConclusion.FAILURE.value
            await validator.save()
            # Continue to iterate to wait for the end of all checks

    validator.state.value = ValidatorState.COMPLETED.value
    validator.completed_at.value = Timestamp().to_string()
    if validator.conclusion.value != ValidatorConclusion.FAILURE.value:
        validator.conclusion.value = ValidatorConclusion.SUCCESS.value

    await validator.save()
