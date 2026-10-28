from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreProposedChange, CoreReadOnlyRepository
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo, GitRepoType
from infrahub_sdk.testing.schemas.car_person import TESTING_MANUFACTURER, SchemaCarPerson
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterExpectedStartTime,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.responses import OrchestrationResult, SetStateStatus
from prefect.events.schemas.events import Event, Resource
from prefect.states import Cancelled, Scheduled

from infrahub.prefect_server.retention import PREFECT_EVENT_TYPES
from tests.helpers.fixtures import get_fixtures_dir

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.schema import SchemaRoot
    from infrahub_testcontainers.container import InfrahubDockerCompose
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun

pytestmark = pytest.mark.shard_b

WORKLOAD_EVENT_TYPES = {"prefect.flow-run.Completed", "prefect.flow-run.Failed", "prefect.flow-run.Cancelled"}
WORKER_STARTED = "prefect.worker.started"
# Its `infrahub.` prefix keeps it out of the Prefect event types that the tests and the startup check read.
SETTLED_MARKER_EVENT = "infrahub.test.event-types-settled"
EVENT_WAIT_SECONDS = 180
RUNNING_FLOW_WAIT_SECONDS = 60
# Short enough that a missing warning raises within the test timeout, after the workload.
TASK_MANAGER_RESTART_WAIT_SECONDS = 120
# Six flush intervals of the task manager's event persister.
SETTLED_MARKER_WAIT_SECONDS = 30
POLL_SECONDS = 1

CANCELLED_RUN_DEPLOYMENT = "git_repositories_sync/git_repositories_sync"
UNLISTED_PREFECT_EVENT = "prefect.infrahub-test.unlisted"
UNLISTED_WARNING = (
    "Task manager retention: Infrahub does not list these Prefect event types, so they are kept for the activity log "
    f"retention (7 days) instead of prefect_own_events: {UNLISTED_PREFECT_EVENT}"
)
STARTUP_CHECK_FAILED = "Task manager retention: could not read the stored event types"
_DELETE_UNLISTED_PREFECT_EVENTS = (
    "DELETE FROM event_resources WHERE event_id IN "
    "(SELECT id FROM events WHERE event = 'prefect.infrahub-test.unlisted'); "
    "DELETE FROM events WHERE event = 'prefect.infrahub-test.unlisted'"
)

_STORED_PREFECT_EVENTS_QUERY = "SELECT event, count(*) FROM events WHERE event NOT LIKE 'infrahub.%' GROUP BY event"


async def _poll_until(
    *, condition: Callable[[], Awaitable[bool]], waiting_for: str, seconds: float, interval: float = POLL_SECONDS
) -> None:
    """Await the condition every interval until it holds.

    Raises:
        TimeoutError: When the condition does not hold within the given seconds.

    """
    deadline = time.monotonic() + seconds
    while not await condition():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Waited {seconds} s for {waiting_for}")
        await asyncio.sleep(interval)


async def _query_task_manager_database(compose: InfrahubDockerCompose, query: str) -> list[str]:
    """The rows the query returns from the task manager's database, one line per row with `|` between columns."""
    stdout, _, _ = await asyncio.to_thread(
        compose.exec_in_container,
        command=["psql", "--username=postgres", "--dbname=prefect", "--tuples-only", "--no-align", "-c", query],
        service_name="task-manager-db",
    )
    return stdout.strip().splitlines()


async def _stored_prefect_events(compose: InfrahubDockerCompose) -> dict[str, int]:
    """The number of stored events of each type that does not start with `infrahub.`."""
    rows = await _query_task_manager_database(compose=compose, query=_STORED_PREFECT_EVENTS_QUERY)
    return {event: int(count) for event, count in (row.split("|") for row in rows)}


async def _wait_for_stored_event_types(compose: InfrahubDockerCompose, event_types: set[str]) -> None:
    async def _stored() -> bool:
        return event_types <= set(await _stored_prefect_events(compose=compose))

    await _poll_until(
        condition=_stored, waiting_for=f"the task manager to store {sorted(event_types)}", seconds=EVENT_WAIT_SECONDS
    )


def _delete_unlisted_prefect_events(compose: InfrahubDockerCompose) -> None:
    compose.exec_in_container(
        command=["psql", "--username=postgres", "--dbname=prefect", "-c", _DELETE_UNLISTED_PREFECT_EVENTS],
        service_name="task-manager-db",
    )


async def _task_manager_log_lines_with(compose: InfrahubDockerCompose, text: str) -> list[str]:
    stdout, stderr = await asyncio.to_thread(compose.get_logs, "task-manager")
    return [line for line in f"{stdout}\n{stderr}".splitlines() if text in line]


async def _wait_for_task_manager_log_line(compose: InfrahubDockerCompose, text: str) -> None:
    async def _logged() -> bool:
        return bool(await _task_manager_log_lines_with(compose=compose, text=text))

    await _poll_until(
        condition=_logged, waiting_for=f"the task manager to log {text!r}", seconds=TASK_MANAGER_RESTART_WAIT_SECONDS
    )


async def _wait_for_worker_restart(compose: InfrahubDockerCompose, started_before: int) -> None:
    async def _restarted() -> bool:
        return (await _stored_prefect_events(compose=compose)).get(WORKER_STARTED, 0) > started_before

    await _poll_until(
        condition=_restarted,
        waiting_for=f"a {WORKER_STARTED} event from the restarted task worker",
        seconds=EVENT_WAIT_SECONDS,
    )


async def _wait_for_a_running_flow_run(prefect_client: PrefectClient) -> None:
    running = FlowRunFilter(state=FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType.RUNNING])))

    async def _a_run_is_running() -> bool:
        return bool(await prefect_client.read_flow_runs(flow_run_filter=running))

    await _poll_until(
        condition=_a_run_is_running,
        waiting_for="a running flow run",
        seconds=RUNNING_FLOW_WAIT_SECONDS,
        interval=POLL_SECONDS / 4,
    )


async def _unsettled_flow_runs(prefect_client: PrefectClient) -> list[FlowRun]:
    """The flow runs that are pending, running, or scheduled to start by now."""
    unsettled = FlowRunFilter(
        state=FlowRunFilterState(
            type=FlowRunFilterStateType(any_=[StateType.SCHEDULED, StateType.PENDING, StateType.RUNNING])
        ),
        expected_start_time=FlowRunFilterExpectedStartTime(before_=datetime.now(UTC)),
    )
    return await prefect_client.read_flow_runs(flow_run_filter=unsettled)


async def _post_event(prefect_client: PrefectClient, event_type: str) -> uuid.UUID:
    """Post an event of the given type to the task manager and return its id."""
    event = Event(
        id=uuid.uuid4(),
        event=event_type,
        resource=Resource({"prefect.resource.id": f"infrahub-test.{uuid.uuid4()}"}),
    )
    response = await prefect_client._client.post("/events", json=[event.model_dump(mode="json")])
    response.raise_for_status()
    return event.id


async def _event_is_stored(compose: InfrahubDockerCompose, event_id: uuid.UUID) -> bool:
    query = f"SELECT count(*) FROM events WHERE id = '{event_id}'"  # noqa: S608 - an id the test generated
    return await _query_task_manager_database(compose=compose, query=query) == ["1"]


async def _wait_for_stored_marker(compose: InfrahubDockerCompose, prefect_client: PrefectClient) -> None:
    """Post a marker event and wait until the task manager stores it."""
    marker_id = await _post_event(prefect_client=prefect_client, event_type=SETTLED_MARKER_EVENT)

    async def _stored() -> bool:
        return await _event_is_stored(compose=compose, event_id=marker_id)

    await _poll_until(
        condition=_stored,
        waiting_for=f"the task manager to store the event {marker_id}",
        seconds=SETTLED_MARKER_WAIT_SECONDS,
    )


async def _wait_until_settled(compose: InfrahubDockerCompose, prefect_client: PrefectClient) -> None:
    """Wait until no flow run is left to run and the task manager has stored every event it received.

    Raises:
        TimeoutError: When a flow run is still pending, running or due at the deadline, or the task manager does not
            store the marker event in time.

    """
    deadline = time.monotonic() + EVENT_WAIT_SECONDS
    while True:
        unsettled = await _unsettled_flow_runs(prefect_client=prefect_client)
        if not unsettled:
            # The task manager stores events in arrival order, so the marker is stored after every earlier event.
            await _wait_for_stored_marker(compose=compose, prefect_client=prefect_client)
            # A run that started while the marker waited sends events that the marker does not cover.
            unsettled = await _unsettled_flow_runs(prefect_client=prefect_client)
            if not unsettled:
                return
        if time.monotonic() >= deadline:
            names = ", ".join(sorted(f"{run.name} ({run.state_name})" for run in unsettled))
            raise TimeoutError(f"Flow runs not finished after {EVENT_WAIT_SECONDS} s: {names}")
        await asyncio.sleep(POLL_SECONDS)


class TestPrefectEventTypes(TestInfrahubDockerClient, SchemaCarPerson):
    @pytest.fixture(scope="class")
    async def stored_prefect_event_types(
        self,
        client: InfrahubClient,
        prefect_client: PrefectClient,
        infrahub_compose: InfrahubDockerCompose,
        remote_repos_dir: Path,
        schema_base: SchemaRoot,
    ) -> set[str]:
        """The Prefect event types stored after a workload with a failed run, a cancelled run and a worker restart.

        Raises:
            RuntimeError: When the task manager refuses to cancel the scheduled run.

        """
        await client.schema.load(schemas=[schema_base.to_schema_dict()], wait_until_converged=True)
        persons = await self.create_persons(client=client, branch="main")
        persons[0].height.value = 180
        await persons[0].save()

        branch = await client.branch.create(branch_name="event-types-merge", sync_with_git=False)
        await self.create_manufacturers(client=client, branch=branch.name)
        await client.branch.rebase(branch_name=branch.name)
        await client.branch.merge(branch_name=branch.name)

        # The connectivity check does not resolve a read-only repository's ref, so only the add flow fails on it.
        source = GitRepo(
            name="missing-ref",
            src_directory=get_fixtures_dir() / "repos" / "read-only-repo" / "initial__main",
            dst_directory=remote_repos_dir,
            type=GitRepoType.READ_ONLY,
        )
        repository = await client.create(
            kind=CoreReadOnlyRepository,
            name=source.name,
            location=f"{source.remote_directory_name}/{source.name}",
            ref="missing-ref",
        )
        await repository.save()

        deployment = await prefect_client.read_deployment_by_name(name=CANCELLED_RUN_DEPLOYMENT)
        scheduled = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id, state=Scheduled(scheduled_time=datetime.now(UTC) + timedelta(days=1))
        )
        cancellation: OrchestrationResult[None] = await prefect_client.set_flow_run_state(
            flow_run_id=scheduled.id, state=Cancelled()
        )
        if cancellation.status != SetStateStatus.ACCEPT:
            raise RuntimeError(f"The task manager answered {cancellation.status} to cancelling a scheduled run")

        await _wait_for_stored_event_types(compose=infrahub_compose, event_types=WORKLOAD_EVENT_TYPES)

        proposed_branch = await client.branch.create(branch_name="event-types-proposed-change", sync_with_git=False)
        manufacturer = await client.create(kind=TESTING_MANUFACTURER, name="Toyota", branch=proposed_branch.name)
        await manufacturer.save()
        proposed_change = await client.create(
            kind=CoreProposedChange,
            name="event-types",
            source_branch=proposed_branch.name,
            destination_branch="main",
        )
        await proposed_change.save()

        # A task worker stopped while a run is running reports that run crashed.
        await _wait_for_a_running_flow_run(prefect_client=prefect_client)
        started_before = (await _stored_prefect_events(compose=infrahub_compose)).get(WORKER_STARTED, 0)
        infrahub_compose._run_command(cmd=[*infrahub_compose.compose_command_property, "restart", "task-worker"])
        await _wait_for_worker_restart(compose=infrahub_compose, started_before=started_before)

        await _wait_until_settled(compose=infrahub_compose, prefect_client=prefect_client)
        return set(await _stored_prefect_events(compose=infrahub_compose))

    def test_every_stored_prefect_event_type_is_listed(self, stored_prefect_event_types: set[str]) -> None:
        """Every Prefect event type the workload stores is in the list given its own retention."""
        assert sorted(stored_prefect_event_types - set(PREFECT_EVENT_TYPES)) == []

    def test_the_workload_stores_completed_failed_and_cancelled_runs(
        self, stored_prefect_event_types: set[str]
    ) -> None:
        """The workload stores completed, failed and cancelled flow runs, so a quiet stack cannot pass the guard."""
        # Cron runs, heartbeats and the worker restart add types that vary between runs, so only these are pinned.
        assert sorted(WORKLOAD_EVENT_TYPES - stored_prefect_event_types) == []

    async def test_a_restarted_task_manager_warns_about_a_stored_prefect_event_type_missing_from_the_list(
        self,
        stored_prefect_event_types: set[str],
        prefect_client: PrefectClient,
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        """At startup the task manager names the stored Prefect event types missing from the list, read on Postgres.

        It requests the workload so that the task manager restarts only after the workload has run.
        """
        try:
            await _post_event(prefect_client=prefect_client, event_type=UNLISTED_PREFECT_EVENT)
            await _wait_for_stored_event_types(compose=infrahub_compose, event_types={UNLISTED_PREFECT_EVENT})
            infrahub_compose._run_command(cmd=[*infrahub_compose.compose_command_property, "restart", "task-manager"])
            await _wait_for_task_manager_log_line(compose=infrahub_compose, text=UNLISTED_WARNING)
        finally:
            _delete_unlisted_prefect_events(compose=infrahub_compose)

        assert len(await _task_manager_log_lines_with(compose=infrahub_compose, text=UNLISTED_WARNING)) == 1
        assert await _task_manager_log_lines_with(compose=infrahub_compose, text=STARTUP_CHECK_FAILED) == []
