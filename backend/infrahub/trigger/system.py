"""System-level Prefect automations.

This module contains system automations that manage Prefect infrastructure,
such as detecting and crashing zombie flow runs.
"""

from datetime import timedelta

from prefect.client.schemas.objects import StateType

from infrahub.trigger.models import ChangeFlowRunStateAction, ProactiveEventTrigger, SystemTriggerDefinition
from infrahub.webhook.constants import WEBHOOK_SEND_RETRY_DELAY_SECONDS

# The two event sets below do opposite things. An event in `after` restarts the per-run countdown;
# an event that is only expected satisfies the window instead, so it expires without firing and
# the run is left unwatched. Ending the watch that way is only ever right for a finished run.
ZOMBIE_WATCH_ENDING_EVENTS: set[str] = {
    "prefect.flow-run.Completed",
    "prefect.flow-run.Failed",
    "prefect.flow-run.Cancelled",
    "prefect.flow-run.Crashed",
}

# Every other expected event means the run is still alive and must renew the countdown. A retry
# wait is silent for its whole duration -- the engine tears down its heartbeat thread before it
# sleeps out the delay -- so the transition anchors the countdown at the start of that silence.
ZOMBIE_WATCH_RENEWING_EVENTS: set[str] = {
    "prefect.flow-run.heartbeat",
    "prefect.flow-run.AwaitingRetry",
}

# The window must outlast the longest configured backoff or a legitimate retry wait is mistaken
# for a dead process. The margin absorbs propagation and scheduler jitter before the resumed
# run's first heartbeat.
ZOMBIE_DETECTION_MARGIN = timedelta(seconds=60)
ZOMBIE_HEARTBEAT_WINDOW = timedelta(seconds=WEBHOOK_SEND_RETRY_DELAY_SECONDS) + ZOMBIE_DETECTION_MARGIN

TRIGGER_CRASH_ZOMBIE_FLOWS = SystemTriggerDefinition(
    name="crash-zombie-flows",
    description="Crashes flow runs that have stopped sending heartbeats",
    trigger=ProactiveEventTrigger(
        after=ZOMBIE_WATCH_RENEWING_EVENTS,
        events=ZOMBIE_WATCH_RENEWING_EVENTS | ZOMBIE_WATCH_ENDING_EVENTS,
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
