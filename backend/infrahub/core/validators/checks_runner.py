import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any

from infrahub_sdk.protocols import CoreValidator

from infrahub.artifacts.render_lock import validator_lock
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID, ValidatorConclusion, ValidatorState
from infrahub.core.protocols import CoreCheck, CoreProposedChange
from infrahub.core.protocols import CoreValidator as CoreValidatorNode
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.events.models import EventContext
from infrahub.log import get_logger
from infrahub.services.adapters.event import InfrahubEventService
from infrahub.utils import InfrahubStringEnum
from infrahub.validators.events import send_failed_validator, send_passed_validator


class CheckPending(InfrahubStringEnum):
    """Result of a check whose conclusion is written to the stored check later, by another process."""

    PENDING = "pending"


type CheckResult = ValidatorConclusion | CheckPending


async def run_checks_and_update_validator(
    checks: Sequence[Coroutine[Any, Any, CheckResult]],
    validator: CoreValidator,
    context: InfrahubContext,
    event_service: InfrahubEventService,
    proposed_change_id: str,
) -> bool:
    """Execute a list of checks coroutines, and set validator fields accordingly.

    Tasks are retrieved by completion order so as soon as we detect a failing check,
    we set validator conclusion to failure. A check that raises counts as a failing check.

    Returns True, and leaves the validator in progress, when a check is pending; the validator is then completed
    later from its stored checks.
    """
    event_context = context.to_event_context()

    # First set validator to in progress, then wait for results
    validator.state.value = ValidatorState.IN_PROGRESS.value
    validator.started_at.value = Timestamp().to_string()
    validator.completed_at.value = ""
    await validator.save()

    failed_early = False
    pending = False

    for earliest_task in asyncio.as_completed(checks):
        # One check run that fails or times out must fail the validator, not leave it in progress.
        try:
            result = await earliest_task
        except Exception:  # noqa: BLE001
            get_logger().exception("A check run failed", validator_id=validator.id)
            result = ValidatorConclusion.FAILURE
        if validator.conclusion.value != ValidatorConclusion.FAILURE.value and result == ValidatorConclusion.FAILURE:
            validator.conclusion.value = ValidatorConclusion.FAILURE.value
            failed_early = True
            await validator.save()
            await send_failed_validator(
                event_service=event_service,
                validator=validator,
                proposed_change_id=proposed_change_id,
                context=event_context,
            )
            # Continue to iterate to wait for the end of all checks
        if result == CheckPending.PENDING:
            pending = True

    if pending:
        return True

    validator.state.value = ValidatorState.COMPLETED.value
    validator.completed_at.value = Timestamp().to_string()
    if validator.conclusion.value != ValidatorConclusion.FAILURE.value:
        validator.conclusion.value = ValidatorConclusion.SUCCESS.value

    await validator.save()

    if not failed_early:
        if validator.conclusion.value == ValidatorConclusion.SUCCESS.value:
            await send_passed_validator(
                event_service=event_service,
                validator=validator,
                proposed_change_id=proposed_change_id,
                context=event_context,
            )
        else:
            await send_failed_validator(
                event_service=event_service,
                validator=validator,
                proposed_change_id=proposed_change_id,
                context=event_context,
            )

    return False


async def recompute_validator(
    db: InfrahubDatabase, event_service: InfrahubEventService, validator_id: str, context: EventContext
) -> None:
    """Complete the validator from its stored checks once none of them is still waiting for a conclusion.

    Sends the failed validator event only when the stored conclusion was not already a failure, since that event
    was sent when the first check failed.
    """
    async with validator_lock(validator_id=validator_id):
        validator = await registry.manager.get_one(db=db, id=validator_id, kind=CoreValidatorNode)
        if validator is None or validator.get_attribute("state").get_value() == ValidatorState.COMPLETED.value:
            return
        checks = await validator.checks.get_peers(db=db, peer_type=CoreCheck)
        conclusions = {check.get_attribute("conclusion").get_value() for check in checks.values()}
        if ValidatorConclusion.UNKNOWN.value in conclusions:
            return

        previous_conclusion = validator.get_attribute("conclusion").get_value()
        conclusion = (
            ValidatorConclusion.FAILURE
            if ValidatorConclusion.FAILURE.value in conclusions
            else ValidatorConclusion.SUCCESS
        )
        validator.get_attribute("state").value = ValidatorState.COMPLETED.value
        validator.get_attribute("conclusion").value = conclusion.value
        validator.completed_at.value = Timestamp().to_string()
        await validator.save(db=db, user_id=SYSTEM_USER_ID)

        proposed_change = await validator.proposed_change.get_peer(
            db=db, peer_type=CoreProposedChange, raise_on_error=True
        )
        if conclusion == ValidatorConclusion.SUCCESS:
            await send_passed_validator(
                event_service=event_service, validator=validator, proposed_change_id=proposed_change.id, context=context
            )
        elif previous_conclusion != ValidatorConclusion.FAILURE.value:
            await send_failed_validator(
                event_service=event_service, validator=validator, proposed_change_id=proposed_change.id, context=context
            )
