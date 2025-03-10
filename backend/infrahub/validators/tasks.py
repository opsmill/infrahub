from typing import Any, TypeVar, cast

from infrahub_sdk.protocols import CoreValidator

from infrahub.context import InfrahubContext
from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.services import InfrahubServices

from .events import send_start_validator

ValidatorType = TypeVar("ValidatorType", bound=CoreValidator)


async def start_validator(
    service: InfrahubServices,
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
        validator = await service.client.create(
            kind=validator_type,
            data=data,
        )
        await validator.save()

    await send_start_validator(
        service=service, validator=validator, proposed_change_id=proposed_change, context=context
    )

    return validator
