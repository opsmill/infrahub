# ruff: noqa: INP001  # standalone manual-testing script, not a package module
"""Ad-hoc telemetry window probe (manual testing aid; not part of the app or tests).

Counts one activity_24h metric across three windows so a just-now action can be confirmed
without waiting for the calendar day to roll:

  YESTERDAY  -> the window today's telemetry snapshot reports
  TODAY      -> the window tomorrow's snapshot will report (where an action done now lands)
  LAST 3H    -> a tight window around right now, to isolate the action you just took

Run inside a worker container (has the Prefect client + PREFECT_API_URL):

  docker exec infrahub-task-worker-1 python /source/dev/specs/telemetry-collection-infp-589/window_probe.py [metric]

`metric` defaults to `logins`. Event-based metrics: logins, branches_created/merged/deleted,
checks_started/passed/failed, artifacts_created/updated (or a raw Prefect event name).
The special metric `webhooks` counts webhook-process flow-runs and reports success/failure.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from prefect.client.orchestration import PrefectClient, get_client

from infrahub.events.account_action import AccountLoggedInEvent
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.branch_action import BranchCreatedEvent, BranchDeletedEvent, BranchMergedEvent
from infrahub.events.validator_action import ValidatorFailedEvent, ValidatorPassedEvent, ValidatorStartedEvent
from infrahub.telemetry.task_manager import count_webhook_runs, count_windowed_event, count_windowed_unique_resources
from infrahub.telemetry.utils import get_activity_window

EVENTS = {
    "logins": AccountLoggedInEvent.event_name,
    "branches_created": BranchCreatedEvent.event_name,
    "branches_merged": BranchMergedEvent.event_name,
    "branches_deleted": BranchDeletedEvent.event_name,
    "checks_started": ValidatorStartedEvent.event_name,
    "checks_passed": ValidatorPassedEvent.event_name,
    "checks_failed": ValidatorFailedEvent.event_name,
    "artifacts_created": ArtifactCreatedEvent.event_name,
    "artifacts_updated": ArtifactUpdatedEvent.event_name,
}

key = sys.argv[1] if len(sys.argv) > 1 else "logins"


def windows_for(now: datetime) -> dict[str, tuple[datetime, datetime]]:
    return {
        "YESTERDAY (today's snapshot)": get_activity_window(now),
        "TODAY (tomorrow's snapshot) ": get_activity_window(now + timedelta(days=1)),
        "LAST 3H  (activity just now)": (now - timedelta(hours=3), now),
    }


async def probe_webhooks(client: PrefectClient, windows: dict[str, tuple[datetime, datetime]]) -> None:
    for label, (start, end) in windows.items():
        success, failure = await count_webhook_runs.fn(client=client, window_start=start, window_end=end)
        print(f"{label}  success={success} failure={failure}")


async def probe_event(client: PrefectClient, event: str, windows: dict[str, tuple[datetime, datetime]]) -> None:
    for label, (start, end) in windows.items():
        total = await count_windowed_event.fn(client=client, event_name=event, window_start=start, window_end=end)
        unique = await count_windowed_unique_resources.fn(
            client=client, event_name=event, window_start=start, window_end=end
        )
        print(f"{label}  count={total} unique={unique}")


async def main() -> None:
    now = datetime.now(tz=UTC)
    windows = windows_for(now)
    print(f"metric: {key}")
    print(f"now   : {now.isoformat()}\n")
    async with get_client(sync_client=False) as client:
        if key == "webhooks":
            await probe_webhooks(client, windows)
        else:
            await probe_event(client, EVENTS.get(key, key), windows)


asyncio.run(main())
