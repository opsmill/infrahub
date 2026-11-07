from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from prefect import State
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import ArtifactCreate
from prefect.client.schemas.filters import ArtifactFilter, FlowFilter, FlowRunFilter, LogFilter
from prefect.client.schemas.objects import Artifact, Flow, FlowRun, Log, StateType
from prefect.client.schemas.sorting import FlowRunSort
from prefect.events.filters import EventFilter, EventNameFilter, EventOccurredFilter, EventResourceFilter
from prefect.types import DateTime

CANCEL_REQUEST_STATE_TYPES = frozenset({StateType.CANCELLING, StateType.CANCELLED})
FLOW_RUN_HEARTBEAT_EVENT = "prefect.flow-run.heartbeat"
FLOW_RUN_RESOURCE_PREFIX = "prefect.flow-run."
# The events API rejects a page size above 50.
EVENTS_PAGE_SIZE = 50


class FlowRunQuerying(Protocol):
    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]: ...


class FlowRunDataReading(Protocol):
    async def read_logs(self, log_filter: LogFilter, offset: int, limit: int) -> list[Log]: ...

    async def read_artifacts(
        self,
        artifact_filter: ArtifactFilter,
        flow_run_filter: FlowRunFilter,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Artifact]: ...

    async def read_flows(self, flow_filter: FlowFilter | None = None) -> list[Flow]: ...


class FlowRunArtifactWriting(Protocol):
    async def create_artifact(self, key: str, artifact_type: str, data: Any, flow_run_id: UUID) -> None: ...


class FlowRunCounting(Protocol):
    async def count_flow_runs(self, body: dict[str, Any]) -> int: ...


class FlowRunMaintenance(Protocol):
    async def delete_flow_run(self, flow_run_id: UUID) -> None: ...

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> StateType | None:
        """Request a state transition, returning the state the run ended in after orchestration."""
        ...


class FlowRunCancellationReading(Protocol):
    async def cancellation_requested(self, flow_run_id: UUID) -> bool:
        """Return whether a cancellation was ever recorded for the flow run.

        The state history is consulted rather than the current state, because a transition that
        happens after the cancellation (such as a retry resuming) overwrites the current state
        while the recorded request remains in the history.
        """
        ...


class FlowRunHeartbeatReading(Protocol):
    async def flow_runs_with_heartbeat_since(self, flow_run_ids: Sequence[UUID], since: DateTime) -> set[UUID]:
        """Return the flow runs among `flow_run_ids` that sent a heartbeat at or after `since`."""
        ...

    async def latest_event_occurred(self, since: DateTime) -> DateTime | None:
        """Return when the newest stored event occurred, or `None` when no event stored occurred after `since`."""
        ...


class ReaderPrefectClient(FlowRunQuerying, FlowRunDataReading, Protocol): ...


class WriterPrefectClient(FlowRunArtifactWriting, Protocol): ...


class RetentionPrefectClient(FlowRunQuerying, FlowRunMaintenance, Protocol): ...


class ZombieReaperPrefectClient(FlowRunQuerying, FlowRunMaintenance, FlowRunHeartbeatReading, Protocol): ...


class PrefectClientAdapter:
    """Adapt a Prefect client to the operations the flow-run feature relies on."""

    def __init__(self, client: PrefectClient) -> None:
        self.client = client

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        return await self.client.read_flow_runs(
            flow_filter=flow_filter, flow_run_filter=flow_run_filter, limit=limit, offset=offset, sort=sort
        )

    async def read_logs(self, log_filter: LogFilter, offset: int, limit: int) -> list[Log]:
        return await self.client.read_logs(log_filter=log_filter, offset=offset, limit=limit)

    async def read_artifacts(
        self,
        artifact_filter: ArtifactFilter,
        flow_run_filter: FlowRunFilter,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Artifact]:
        return await self.client.read_artifacts(
            artifact_filter=artifact_filter, flow_run_filter=flow_run_filter, limit=limit, offset=offset
        )

    async def create_artifact(self, key: str, artifact_type: str, data: Any, flow_run_id: UUID) -> None:
        await self.client.create_artifact(
            artifact=ArtifactCreate(key=key, type=artifact_type, data=data, flow_run_id=flow_run_id)
        )

    async def read_flows(self, flow_filter: FlowFilter | None = None) -> list[Flow]:
        if flow_filter is None:
            return await self.client.read_flows()
        return await self.client.read_flows(flow_filter=flow_filter)

    async def count_flow_runs(self, body: dict[str, Any]) -> int:
        response = await self.client._client.post("/flow_runs/count", json=body)
        response.raise_for_status()
        return int(response.json())

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        await self.client.delete_flow_run(flow_run_id=flow_run_id)

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> StateType | None:
        result = await self.client.set_flow_run_state(flow_run_id=flow_run_id, state=state, force=force)
        return result.state.type if result.state else None

    async def cancellation_requested(self, flow_run_id: UUID) -> bool:
        states = await self.client.read_flow_run_states(flow_run_id=flow_run_id)
        return any(state.type in CANCEL_REQUEST_STATE_TYPES for state in states)

    async def flow_runs_with_heartbeat_since(self, flow_run_ids: Sequence[UUID], since: DateTime) -> set[UUID]:
        if not flow_run_ids:
            return set()
        event_filter = EventFilter(
            occurred=EventOccurredFilter(since=since),
            event=EventNameFilter(name=[FLOW_RUN_HEARTBEAT_EVENT]),
            resource=EventResourceFilter(
                id=[f"{FLOW_RUN_RESOURCE_PREFIX}{flow_run_id}" for flow_run_id in flow_run_ids]
            ),
        )
        heartbeating: set[UUID] = set()
        page = await self.client.read_events(filter=event_filter, limit=EVENTS_PAGE_SIZE)
        while True:
            heartbeating.update(UUID(event.resource.id.removeprefix(FLOW_RUN_RESOURCE_PREFIX)) for event in page.events)
            if page.next_page is None:
                return heartbeating
            page = await self.client.read_events_page(next_page_url=str(page.next_page))

    async def latest_event_occurred(self, since: DateTime) -> DateTime | None:
        page = await self.client.read_events(filter=EventFilter(occurred=EventOccurredFilter(since=since)), limit=1)
        return page.events[0].occurred if page.events else None
