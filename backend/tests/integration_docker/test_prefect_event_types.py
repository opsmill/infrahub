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
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterState, FlowRunFilterStateType
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.responses import OrchestrationResult, SetStateStatus
from prefect.events.schemas.events import Event, Resource
from prefect.states import Cancelled, Scheduled

from infrahub.prefect_server.retention import PREFECT_EVENT_TYPES
from tests.helpers.fixtures import get_fixtures_dir

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.schema import SchemaRoot
    from infrahub_testcontainers.container import InfrahubDockerCompose
    from prefect.client.orchestration import PrefectClient

pytestmark = pytest.mark.shard_b

WORKLOAD_EVENT_TYPES = {"prefect.flow-run.Completed", "prefect.flow-run.Failed", "prefect.flow-run.Cancelled"}
WORKER_STARTED = "prefect.worker.started"
EVENT_WAIT_SECONDS = 180
RUNNING_FLOW_WAIT_SECONDS = 60
# Short enough that a missing warning fails on its assertion within the test timeout, after the workload.
TASK_MANAGER_RESTART_WAIT_SECONDS = 120
# Three flush intervals of the task manager's event persister, so events emitted just before the read are stored.
EVENT_PERSISTER_SETTLE_SECONDS = 15
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


def _stored_prefect_events(compose: InfrahubDockerCompose) -> dict[str, int]:
    """The number of stored events of each type that does not start with `infrahub.`."""
    stdout, _, _ = compose.exec_in_container(
        command=[
            "psql",
            "--username=postgres",
            "--dbname=prefect",
            "--tuples-only",
            "--no-align",
            "-c",
            _STORED_PREFECT_EVENTS_QUERY,
        ],
        service_name="task-manager-db",
    )
    return {event: int(count) for event, count in (line.split("|") for line in stdout.strip().splitlines())}


async def _wait_for_stored_event_types(compose: InfrahubDockerCompose, event_types: set[str]) -> None:
    deadline = time.monotonic() + EVENT_WAIT_SECONDS
    while time.monotonic() < deadline:
        if event_types <= set(_stored_prefect_events(compose=compose)):
            return
        await asyncio.sleep(POLL_SECONDS)


def _delete_unlisted_prefect_events(compose: InfrahubDockerCompose) -> None:
    compose.exec_in_container(
        command=["psql", "--username=postgres", "--dbname=prefect", "-c", _DELETE_UNLISTED_PREFECT_EVENTS],
        service_name="task-manager-db",
    )


def _task_manager_log_lines_with(compose: InfrahubDockerCompose, text: str) -> list[str]:
    stdout, stderr = compose.get_logs("task-manager")
    return [line for line in f"{stdout}\n{stderr}".splitlines() if text in line]


async def _wait_for_task_manager_log_line(compose: InfrahubDockerCompose, text: str) -> None:
    deadline = time.monotonic() + TASK_MANAGER_RESTART_WAIT_SECONDS
    while time.monotonic() < deadline:
        if _task_manager_log_lines_with(compose=compose, text=text):
            return
        await asyncio.sleep(POLL_SECONDS)


async def _wait_for_worker_restart(compose: InfrahubDockerCompose, started_before: int) -> None:
    deadline = time.monotonic() + EVENT_WAIT_SECONDS
    while time.monotonic() < deadline:
        if _stored_prefect_events(compose=compose).get(WORKER_STARTED, 0) > started_before:
            return
        await asyncio.sleep(POLL_SECONDS)


async def _wait_for_a_running_flow_run(prefect_client: PrefectClient) -> None:
    running = FlowRunFilter(state=FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType.RUNNING])))
    deadline = time.monotonic() + RUNNING_FLOW_WAIT_SECONDS
    while time.monotonic() < deadline:
        if await prefect_client.read_flow_runs(flow_run_filter=running):
            return
        await asyncio.sleep(POLL_SECONDS / 4)


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
        started_before = _stored_prefect_events(compose=infrahub_compose).get(WORKER_STARTED, 0)
        infrahub_compose._run_command(cmd=[*infrahub_compose.compose_command_property, "restart", "task-worker"])
        await _wait_for_worker_restart(compose=infrahub_compose, started_before=started_before)

        await asyncio.sleep(EVENT_PERSISTER_SETTLE_SECONDS)
        return set(_stored_prefect_events(compose=infrahub_compose))

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
        event = Event(
            id=uuid.uuid4(),
            event=UNLISTED_PREFECT_EVENT,
            resource=Resource({"prefect.resource.id": f"infrahub-test.{uuid.uuid4()}"}),
        )
        try:
            response = await prefect_client._client.post("/events", json=[event.model_dump(mode="json")])
            response.raise_for_status()
            await _wait_for_stored_event_types(compose=infrahub_compose, event_types={UNLISTED_PREFECT_EVENT})
            infrahub_compose._run_command(cmd=[*infrahub_compose.compose_command_property, "restart", "task-manager"])
            await _wait_for_task_manager_log_line(compose=infrahub_compose, text=UNLISTED_WARNING)
        finally:
            _delete_unlisted_prefect_events(compose=infrahub_compose)

        assert len(_task_manager_log_lines_with(compose=infrahub_compose, text=UNLISTED_WARNING)) == 1
        assert _task_manager_log_lines_with(compose=infrahub_compose, text=STARTUP_CHECK_FAILED) == []
