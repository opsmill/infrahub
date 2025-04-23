from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import TYPE_CHECKING, Collection

from fastapi import APIRouter, FastAPI
from prefect.server.api.server import create_app
from prefect.server.events import triggers as prefect_triggers
from prefect.server.events.schemas.automations import CompoundTrigger

from . import events

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.server.events.schemas.automations import Automation, EventTrigger, Firing
    from prefect.server.events.schemas.events import ReceivedEvent

router = APIRouter(prefix="/infrahub")

router.include_router(events.router)

OVERRIDE_TRIGGER_REFERENCE_MAP: dict[UUID, Automation] = {}


original_act = prefect_triggers.act


def create_infrahub_prefect() -> FastAPI:
    prefect_triggers.find_interested_triggers = find_interested_triggers
    prefect_triggers.act = act
    app = create_app()
    api_app: FastAPI = app.__dict__["api_app"]
    api_app.include_router(router=router)

    return app


async def act(firing: Firing) -> None:
    """Override the act function from Prefect and clear out weak reference to the event automation"""
    await original_act(firing=firing)
    if firing.triggering_event:
        OVERRIDE_TRIGGER_REFERENCE_MAP.pop(firing.triggering_event.id, None)


def find_interested_triggers(event: ReceivedEvent) -> Collection[EventTrigger]:
    """Override the find_interested_triggers function from Prefect in order to consolidate compound triggers"""
    # The 'triggers' dictionary from Prefect is of type dict[TriggerID, EventTrigger]
    # it contains any triggers or automations defined within the prefect environment

    candidates = prefect_triggers.triggers.values()
    interested_triggers = [trigger for trigger in candidates if trigger.covers(event)]
    if not event.event.startswith("infrahub."):
        # If the event isn't from Infrahub we don't need to care about consolidating
        # the compound triggers
        return interested_triggers

    single_event_triggers = [
        interested_trigger
        for interested_trigger in interested_triggers
        if interested_trigger.automation.trigger.type == "event"
    ]
    if len(single_event_triggers) == len(interested_triggers):
        # Return early if we don't have any compound event triggers
        return interested_triggers

    compound_event_triggers = [
        interested_trigger
        for interested_trigger in interested_triggers
        if interested_trigger.automation.trigger.type == "compound"
    ]
    automation_map: dict[UUID, list[EventTrigger]] = {}
    for compound_event_trigger in compound_event_triggers:
        if compound_event_trigger.automation.id not in automation_map:
            automation_map[compound_event_trigger.automation.id] = []
        automation_map[compound_event_trigger.automation.id].append(compound_event_trigger)

    for triggers in automation_map.values():
        if (
            len(triggers) > 0
            and isinstance(triggers[0].automation.trigger, CompoundTrigger)
            and len(triggers) == len(triggers[0].automation.trigger.triggers)
        ):
            trigger = deepcopy(triggers[0])
            # Need to also do a deep copy of the automation as Prefect only stores a weakref
            # and we don't want to modify the original object
            automation = deepcopy(trigger.automation)
            trigger._set_parent(value=automation)
            OVERRIDE_TRIGGER_REFERENCE_MAP[deepcopy(event.id)] = trigger.automation
            trigger.automation.trigger = trigger
            trigger.threshold = 1
            trigger.within = timedelta(0)
            single_event_triggers.append(trigger)

    return single_event_triggers
