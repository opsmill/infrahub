"""System-level Prefect automations.

This module contains system automations that manage Prefect infrastructure,
such as detecting and crashing zombie flow runs.
"""

from datetime import timedelta

from prefect.client.schemas.objects import StateType

from infrahub.trigger.models import ChangeFlowRunStateAction, ProactiveEventTrigger, SystemTriggerDefinition

TRIGGER_CRASH_ZOMBIE_FLOWS = SystemTriggerDefinition(
    name="crash-zombie-flows",
    description="Crashes flow runs that have stopped sending heartbeats",
    trigger=ProactiveEventTrigger(
        after={"prefect.flow-run.heartbeat"},
        events={
            "prefect.flow-run.heartbeat",
            "prefect.flow-run.Completed",
            "prefect.flow-run.Failed",
            "prefect.flow-run.Cancelled",
            "prefect.flow-run.Crashed",
        },
        match={"prefect.resource.id": ["prefect.flow-run.*"]},
        for_each={"prefect.resource.id"},
        threshold=1,
        within=timedelta(seconds=90),
    ),
    actions=[
        ChangeFlowRunStateAction(
            state=StateType.CRASHED,
            message="Flow run marked as crashed due to missing heartbeats.",
        )
    ],
)
