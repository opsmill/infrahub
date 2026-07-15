"""System-level Prefect automations.

This module contains system automations that manage Prefect infrastructure,
such as detecting and crashing zombie flow runs.
"""

from datetime import timedelta

from prefect.client.schemas.objects import StateType

from infrahub.trigger.models import ChangeFlowRunStateAction, ProactiveEventTrigger, SystemTriggerDefinition
from infrahub.webhook.constants import WEBHOOK_SEND_RETRY_DELAY_SECONDS

# A proactive trigger keeps a per-run countdown: every expected event restarts it, and the
# action fires when the countdown lapses. A run waiting out a retry backoff emits nothing at
# all, so the window must outlast the longest configured backoff or every such wait is
# mistaken for a dead process. The retry-wait transition is an expected event so the countdown
# is anchored at the start of the silence it explains. The margin absorbs event-propagation
# and scheduler jitter between the retry-wait transition and the resumed run's next heartbeat.
ZOMBIE_DETECTION_MARGIN = timedelta(seconds=60)
ZOMBIE_HEARTBEAT_WINDOW = timedelta(seconds=WEBHOOK_SEND_RETRY_DELAY_SECONDS) + ZOMBIE_DETECTION_MARGIN

TRIGGER_CRASH_ZOMBIE_FLOWS = SystemTriggerDefinition(
    name="crash-zombie-flows",
    description="Crashes flow runs that have stopped sending heartbeats",
    trigger=ProactiveEventTrigger(
        after={"prefect.flow-run.heartbeat"},
        events={
            "prefect.flow-run.heartbeat",
            "prefect.flow-run.AwaitingRetry",
            "prefect.flow-run.Completed",
            "prefect.flow-run.Failed",
            "prefect.flow-run.Cancelled",
            "prefect.flow-run.Crashed",
        },
        match={"prefect.resource.id": ["prefect.flow-run.*"]},
        for_each={"prefect.resource.id"},
        threshold=1,
        within=ZOMBIE_HEARTBEAT_WINDOW,
    ),
    actions=[
        ChangeFlowRunStateAction(
            state=StateType.CRASHED,
            message="Flow run marked as crashed due to missing heartbeats.",
        )
    ],
)
