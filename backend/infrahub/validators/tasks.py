from typing import Any, TypeVar, cast

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.protocols import CoreValidator

from infrahub.context import InfrahubContext
from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.workers.dependencies import get_event_service

from .events import send_start_validator

ValidatorType = TypeVar("ValidatorType", bound=CoreValidator)


async def start_validator(
    client: InfrahubClient,
    validator: CoreValidator | None,
    validator_type: type[ValidatorType],
    proposed_change: str,
    context: InfrahubContext,
    data: dict[str, Any],
) -> ValidatorType:
    if validator:
        validator.conclusion.value = ValidatorConclusion.UNKNOWN.value
        validator.state.value = ValidatorState.QUEUED.value
        validator.started_at.value = ""
        validator.completed_at.value = ""
        await validator.save()
        validator = cast(ValidatorType, validator)
    else:
        data["proposed_change"] = proposed_change
        validator = await client.create(kind=validator_type, data=data)
        await validator.save()

    event_service = await get_event_service()
    await send_start_validator(
        event_service=event_service, validator=validator, proposed_change_id=proposed_change, context=context
    )

    return validator
