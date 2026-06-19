from typing import Any, Protocol
from uuid import UUID

from prefect import State
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import ArtifactFilter, FlowFilter, FlowRunFilter, LogFilter
from prefect.client.schemas.objects import Artifact, Flow, FlowRun, Log
from prefect.client.schemas.sorting import FlowRunSort


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
        self, artifact_filter: ArtifactFilter, flow_run_filter: FlowRunFilter
    ) -> list[Artifact]: ...

    async def read_flows(self, flow_filter: FlowFilter | None = None) -> list[Flow]: ...


class FlowRunCounting(Protocol):
    async def count_flow_runs(self, body: dict[str, Any]) -> int: ...


class FlowRunMaintenance(Protocol):
    async def delete_flow_run(self, flow_run_id: UUID) -> None: ...

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> None: ...


class ReaderPrefectClient(FlowRunQuerying, FlowRunDataReading, Protocol): ...


class RetentionPrefectClient(FlowRunQuerying, FlowRunMaintenance, Protocol): ...


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

    async def read_artifacts(self, artifact_filter: ArtifactFilter, flow_run_filter: FlowRunFilter) -> list[Artifact]:
        return await self.client.read_artifacts(artifact_filter=artifact_filter, flow_run_filter=flow_run_filter)

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

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> None:
        await self.client.set_flow_run_state(flow_run_id=flow_run_id, state=state, force=force)
