from infrahub_sdk.protocols import CoreValidator

from infrahub.context import InfrahubContext
from infrahub.events.models import EventMeta
from infrahub.events.validator_action import ValidatorFailedEvent, ValidatorPassedEvent, ValidatorStartedEvent
from infrahub.services.adapters.event import InfrahubEventService


async def send_failed_validator(
    event_service: InfrahubEventService, validator: CoreValidator, proposed_change_id: str, context: InfrahubContext
) -> None:
    event = ValidatorFailedEvent(
        node_id=validator.id,
        kind=validator.get_kind(),
        proposed_change_id=proposed_change_id,
        meta=EventMeta.from_context(context=context),
    )
    await event_service.send(event=event)


async def send_passed_validator(
    event_service: InfrahubEventService, validator: CoreValidator, proposed_change_id: str, context: InfrahubContext
) -> None:
    event = ValidatorPassedEvent(
        node_id=validator.id,
        kind=validator.get_kind(),
        proposed_change_id=proposed_change_id,
        meta=EventMeta.from_context(context=context),
    )
    await event_service.send(event=event)


async def send_start_validator(
    event_service: InfrahubEventService, validator: CoreValidator, proposed_change_id: str, context: InfrahubContext
) -> None:
    event = ValidatorStartedEvent(
        node_id=validator.id,
        kind=validator.get_kind(),
        proposed_change_id=proposed_change_id,
        meta=EventMeta.from_context(context=context),
    )
    await event_service.send(event=event)
