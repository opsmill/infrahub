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
from infrahub_testcontainers.container import InfrahubDockerCompose
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
    from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.schema import SchemaRoot
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
EVENTS_LOCK_HOLDER = "event-types-test-events-lock"
EVENTS_LOCK_SECONDS = 60
EVENTS_LOCK_WAIT_SECONDS = 60
# Longer than the lock, so a read without its own time limit waits for the lock to end.
CHECK_DATABASE_TIMEOUT_SECONDS = 120

CANCELLED_RUN_DEPLOYMENT = "git_repositories_sync/git_repositories_sync"
ACTIVITY_LOG_RETENTION = "30d"
UNLISTED_PREFECT_EVENT = "prefect.infrahub-test.unlisted"
UNLISTED_WARNING = (
    "Task manager retention: these stored Prefect event types have no per-type retention in "
    "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES, so they are kept for the activity log retention "
    f"(P30D): {UNLISTED_PREFECT_EVENT}"
)
STARTUP_CHECK_FAILED = "Task manager retention: could not read the stored event types"
# The statements interpolate only this module's constants, so S608 has no input to guard against.
_DELETE_UNLISTED_PREFECT_EVENTS = (
    "DELETE FROM event_resources WHERE event_id IN "  # noqa: S608
    f"(SELECT id FROM events WHERE event = '{UNLISTED_PREFECT_EVENT}'); "
    f"DELETE FROM events WHERE event = '{UNLISTED_PREFECT_EVENT}'"
)
_EVENTS_LOCK_QUERY = (
    "SELECT count(*) FROM pg_locks JOIN pg_stat_activity USING (pid) "  # noqa: S608
    f"WHERE application_name = '{EVENTS_LOCK_HOLDER}' AND relation = 'events'::regclass AND granted"
)
_RELEASE_EVENTS_LOCK_QUERY = (
    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = '{EVENTS_LOCK_HOLDER}'"  # noqa: S608
)

_STORED_PREFECT_EVENTS_QUERY = "SELECT event, count(*) FROM events WHERE event NOT LIKE 'infrahub.%' GROUP BY event"

_STARTUP_CHECK_SCRIPT = """
import asyncio
from prefect.server.database import provide_database_interface
from infrahub.prefect_server.app import apply_infrahub_settings_to_prefect, warn_about_unlisted_prefect_event_types

apply_infrahub_settings_to_prefect()
asyncio.run(warn_about_unlisted_prefect_event_types(db=provide_database_interface()))
"""


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


async def _wait_for_task_manager_log_lines(compose: InfrahubDockerCompose, text: str, count: int) -> None:
    async def _logged() -> bool:
        return len(await _task_manager_log_lines_with(compose=compose, text=text)) >= count

    await _poll_until(
        condition=_logged,
        waiting_for=f"{count} task manager log lines with {text!r}",
        seconds=TASK_MANAGER_RESTART_WAIT_SECONDS,
    )


def _task_manager_web_workers(compose: InfrahubDockerCompose) -> int:
    """The number of web server processes in the task manager container, each of which checks the stored types at startup."""
    return int(compose.get_env_var("INFRAHUB_TESTING_TASKMGR_API_WORKERS"))


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


async def _unsettled_flow_runs(
    prefect_client: PrefectClient, abandoned_pending_run_ids: set[uuid.UUID]
) -> list[FlowRun]:
    """Active or due flow runs, excluding pending claims abandoned by the stopped workers."""
    due = FlowRunFilter(
        state=FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType.SCHEDULED])),
        expected_start_time=FlowRunFilterExpectedStartTime(before_=datetime.now(UTC)),
    )
    # A worker sets a run it claims early to pending before its expected start time, so these have no time condition.
    in_progress = FlowRunFilter(
        state=FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType.PENDING, StateType.RUNNING]))
    )
    # Scheduled runs are read first, so a run that leaves the scheduled state between the two reads is in the second.
    scheduled = await prefect_client.read_flow_runs(flow_run_filter=due)
    runs = {run.id: run for run in [*scheduled, *await prefect_client.read_flow_runs(flow_run_filter=in_progress)]}
    return [
        run for run in runs.values() if run.id not in abandoned_pending_run_ids or run.state_type != StateType.PENDING
    ]


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


async def _wait_until_settled(
    compose: InfrahubDockerCompose, prefect_client: PrefectClient, abandoned_pending_run_ids: set[uuid.UUID]
) -> None:
    """Wait for runs other than abandoned pending claims, and for the received events to be stored.

    Raises:
        TimeoutError: When another flow run is still pending, running or due at the deadline, or the task manager does not
            store the marker event in time.

    """
    deadline = time.monotonic() + EVENT_WAIT_SECONDS
    while True:
        unsettled = await _unsettled_flow_runs(
            prefect_client=prefect_client, abandoned_pending_run_ids=abandoned_pending_run_ids
        )
        if not unsettled:
            # The default stack's one event persister keeps arrival order, so the marker is stored after every
            # earlier event.
            await _wait_for_stored_marker(compose=compose, prefect_client=prefect_client)
            # A run that started while the marker waited sends events that the marker does not cover.
            unsettled = await _unsettled_flow_runs(
                prefect_client=prefect_client, abandoned_pending_run_ids=abandoned_pending_run_ids
            )
            if not unsettled:
                return
        if time.monotonic() >= deadline:
            names = ", ".join(sorted(f"{run.name} ({run.state_name})" for run in unsettled))
            raise TimeoutError(f"Flow runs not finished after {EVENT_WAIT_SECONDS} s: {names}")
        await asyncio.sleep(POLL_SECONDS)


class TestPrefectEventTypes(TestInfrahubDockerClient, SchemaCarPerson):
    @pytest.fixture(scope="class")
    def infrahub_compose(
        self,
        tmp_directory: Path,
        # Requested so that both directories exist before the stack mounts them.
        remote_repos_dir: Path,
        remote_backups_dir: Path,
        infrahub_version: str,
        deployment_type: str | None,
    ) -> Generator[InfrahubDockerCompose, None, None]:
        # The compose file passes this variable from the environment that starts the stack into the task manager.
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG", ACTIVITY_LOG_RETENTION)
            yield InfrahubDockerCompose.init(
                directory=tmp_directory, version=infrahub_version, deployment_type=deployment_type
            )

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
        await asyncio.to_thread(
            infrahub_compose._run_command,
            cmd=[*infrahub_compose.compose_command_property, "stop", "task-worker"],
        )
        # A replacement worker does not resume claims left pending by the stopped workers.
        pending_runs = await prefect_client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType.PENDING]))
            )
        )
        abandoned_pending_run_ids = {run.id for run in pending_runs if run.deployment_id is not None}
        await asyncio.to_thread(
            infrahub_compose._run_command,
            cmd=[*infrahub_compose.compose_command_property, "start", "task-worker"],
        )
        await _wait_for_worker_restart(compose=infrahub_compose, started_before=started_before)

        await _wait_until_settled(
            compose=infrahub_compose,
            prefect_client=prefect_client,
            abandoned_pending_run_ids=abandoned_pending_run_ids,
        )
        return set(await _stored_prefect_events(compose=infrahub_compose))

    @pytest.fixture
    async def events_table_locked(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> AsyncGenerator[None]:
        """The events table locked by another session for a minute, in the mode that a cleanup rewrite takes.

        Raises:
            TimeoutError: When the lock does not show within a minute.

        """
        infrahub_compose._run_command(
            cmd=[
                *infrahub_compose.compose_command_property,
                "exec",
                "--detach",
                "-T",
                "--env",
                f"PGAPPNAME={EVENTS_LOCK_HOLDER}",
                "task-manager-db",
                "psql",
                "--username=postgres",
                "--dbname=prefect",
                "-c",
                f"BEGIN; LOCK TABLE events IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep({EVENTS_LOCK_SECONDS}); COMMIT;",
            ]
        )

        async def _held() -> bool:
            return await _query_task_manager_database(compose=infrahub_compose, query=_EVENTS_LOCK_QUERY) == ["1"]

        # The session outlives a failed wait as well, holding the lock until its sleep ends.
        try:
            await _poll_until(
                condition=_held,
                waiting_for=f"{EVENTS_LOCK_HOLDER} to lock the events table",
                seconds=EVENTS_LOCK_WAIT_SECONDS,
            )
            yield
        finally:
            await _query_task_manager_database(compose=infrahub_compose, query=_RELEASE_EVENTS_LOCK_QUERY)

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
        """At startup each task manager web server process names the stored Prefect event types without a per-type retention once, read on Postgres.

        The stack keeps the activity log for 30 days and Prefect's own events for 7, so the per-type retentions are in
        effect. It requests the workload so that the task manager restarts only after the workload has run.
        """
        workers = _task_manager_web_workers(compose=infrahub_compose)
        try:
            await _post_event(prefect_client=prefect_client, event_type=UNLISTED_PREFECT_EVENT)
            await _wait_for_stored_event_types(compose=infrahub_compose, event_types={UNLISTED_PREFECT_EVENT})
            infrahub_compose._run_command(cmd=[*infrahub_compose.compose_command_property, "restart", "task-manager"])
            await _wait_for_task_manager_log_lines(compose=infrahub_compose, text=UNLISTED_WARNING, count=workers)
        finally:
            _delete_unlisted_prefect_events(compose=infrahub_compose)

        assert len(await _task_manager_log_lines_with(compose=infrahub_compose, text=UNLISTED_WARNING)) == workers
        assert await _task_manager_log_lines_with(compose=infrahub_compose, text=STARTUP_CHECK_FAILED) == []

    @pytest.mark.usefixtures("events_table_locked")
    async def test_the_startup_check_gives_up_while_a_cleanup_rewrite_locks_the_events_table(
        self, infrahub_compose: InfrahubDockerCompose
    ) -> None:
        """While another session locks the events table, the startup check logs once that it could not read the stored types.

        The check runs with a database timeout longer than the lock, so a lock that is still held after the check
        returned shows that the check's own time limit ended the read.
        """
        result = await asyncio.to_thread(
            infrahub_compose._run_command,
            cmd=[
                *infrahub_compose.compose_command_property,
                "exec",
                "-T",
                "--env",
                f"PREFECT_API_DATABASE_TIMEOUT={CHECK_DATABASE_TIMEOUT_SECONDS}",
                "task-manager",
                "python",
                "-c",
                _STARTUP_CHECK_SCRIPT,
            ],
        )

        output = f"{result.stdout.decode()}\n{result.stderr.decode()}"
        assert len([line for line in output.splitlines() if STARTUP_CHECK_FAILED in line]) == 1
        assert await _query_task_manager_database(compose=infrahub_compose, query=_EVENTS_LOCK_QUERY) == ["1"]
