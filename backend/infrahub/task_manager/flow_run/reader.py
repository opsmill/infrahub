from typing import Protocol
from uuid import UUID

from prefect.client.schemas.filters import (
    ArtifactFilter,
    ArtifactFilterType,
    FlowFilter,
    FlowFilterId,
    FlowFilterName,
    FlowRunFilter,
    FlowRunFilterId,
    LogFilter,
    LogFilterFlowRunId,
)
from prefect.client.schemas.objects import Flow, FlowRun
from prefect.client.schemas.sorting import FlowRunSort

from infrahub.log import get_logger

from .models import FlowLogs, FlowProgress
from .prefect_client import ReaderPrefectClient

log = get_logger()

NB_LOGS_LIMIT = 10_000
PREFECT_MAX_LOGS_PER_CALL = 200


class FlowRunReaderProtocol(Protocol):
    async def read_flow_runs(
        self,
        flow_filter: FlowFilter,
        flow_run_filter: FlowRunFilter,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[FlowRun]: ...

    async def read_logs(self, flow_ids: list[UUID], log_limit: int | None, log_offset: int | None) -> FlowLogs: ...

    async def read_progress(self, flow_ids: list[UUID]) -> FlowProgress: ...

    async def read_flows(self, ids: list[UUID] | None = None, names: list[str] | None = None) -> list[Flow]: ...


class FlowRunReader:
    """Read and shape the flow-run data needed to display tasks."""

    def __init__(self, client: ReaderPrefectClient) -> None:
        self.client = client

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter,
        flow_run_filter: FlowRunFilter,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[FlowRun]:
        return await self.client.read_flow_runs(
            flow_filter=flow_filter,
            flow_run_filter=flow_run_filter,
            limit=limit,
            offset=offset or 0,
            sort=FlowRunSort.START_TIME_DESC,
        )

    async def read_logs(self, flow_ids: list[UUID], log_limit: int | None, log_offset: int | None) -> FlowLogs:
        """Return the logs for the given flow runs, honoring log_limit and log_offset.

        At most NB_LOGS_LIMIT logs are returned per request.

        Raises:
            ValueError: When the requested log_limit exceeds NB_LOGS_LIMIT.

        """
        logs_flow = FlowLogs()

        log_limit = log_limit if log_limit is not None else NB_LOGS_LIMIT
        current_offset = log_offset or 0

        if log_limit > NB_LOGS_LIMIT:
            raise ValueError(f"log_limit cannot be greater than {NB_LOGS_LIMIT}")

        all_logs = []

        # Fetch the logs in batches of PREFECT_MAX_LOGS_PER_CALL, as prefect does not allow to fetch more logs at once.
        remaining = min(log_limit, NB_LOGS_LIMIT)
        while remaining > 0:
            batch_limit = min(PREFECT_MAX_LOGS_PER_CALL, remaining)
            logs_batch = await self.client.read_logs(
                log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=flow_ids)),
                offset=current_offset,
                limit=batch_limit,
            )
            all_logs.extend(logs_batch)
            nb_fetched = len(logs_batch)
            if nb_fetched < batch_limit:
                break  # No more logs to fetch

            current_offset += nb_fetched
            remaining -= nb_fetched

        for flow_log in all_logs:
            if flow_log.flow_run_id and flow_log.message != "Finished in state Completed()":
                logs_flow.logs[flow_log.flow_run_id].append(flow_log)

        return logs_flow

    async def read_progress(self, flow_ids: list[UUID]) -> FlowProgress:
        artifacts = await self.client.read_artifacts(
            artifact_filter=ArtifactFilter(type=ArtifactFilterType(any_=["progress"])),
            flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=flow_ids)),
        )
        flow_progress = FlowProgress()
        for artifact in artifacts:
            if artifact.flow_run_id in flow_progress.data:
                log.warning(
                    f"Multiple Progress Artifact found for the flow_run {artifact.flow_run_id}, keeping the first one"
                )
                continue
            if artifact.flow_run_id and isinstance(artifact.data, float):
                flow_progress.data[artifact.flow_run_id] = artifact.data

        return flow_progress

    async def read_flows(self, ids: list[UUID] | None = None, names: list[str] | None = None) -> list[Flow]:
        if not names and not ids:
            return await self.client.read_flows()

        flow_filter = FlowFilter()
        flow_filter.name = FlowFilterName(any_=names) if names else None
        flow_filter.id = FlowFilterId(any_=ids) if ids else None
        return await self.client.read_flows(flow_filter=flow_filter)
