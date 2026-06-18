from datetime import UTC
from typing import Any
from uuid import UUID, uuid4

from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
from prefect.client.schemas.objects import Flow, FlowRun
from prefect.client.schemas.objects import Log as PrefectLog
from prefect.types import DateTime

from infrahub.task_manager.flow_run.filters import FlowRunFilterBuilder
from infrahub.task_manager.flow_run.models import (
    FlowLogs,
    FlowProgress,
    FlowRunFetchOptions,
    FlowRunQueryCriteria,
    RelatedNodesInfo,
)
from infrahub.task_manager.flow_run.service import PrefectTaskService
from infrahub.task_manager.flow_run.tags import WorkflowTagDecoder
from infrahub.workflows.constants import WorkflowTag


class InMemoryFlowRunReader:
    def __init__(
        self,
        flow_runs: list[FlowRun] | None = None,
        logs: FlowLogs | None = None,
        progress: FlowProgress | None = None,
        flows: list[Flow] | None = None,
    ) -> None:
        self._flow_runs = flow_runs or []
        self._logs = logs or FlowLogs()
        self._progress = progress or FlowProgress()
        self._flows = flows or []
        self.read_flow_runs_calls: list[dict[str, Any]] = []
        self.read_logs_calls: list[dict[str, Any]] = []
        self.read_progress_calls: list[dict[str, Any]] = []
        self.read_flows_calls: list[dict[str, Any]] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter,
        flow_run_filter: FlowRunFilter,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[FlowRun]:
        self.read_flow_runs_calls.append(
            {
                "flow_filter": flow_filter,
                "flow_run_filter": flow_run_filter,
                "limit": limit,
                "offset": offset,
            }
        )
        return self._flow_runs

    async def read_logs(self, flow_ids: list[UUID], log_limit: int | None, log_offset: int | None) -> FlowLogs:
        self.read_logs_calls.append({"flow_ids": flow_ids, "log_limit": log_limit, "log_offset": log_offset})
        return self._logs

    async def read_progress(self, flow_ids: list[UUID]) -> FlowProgress:
        self.read_progress_calls.append({"flow_ids": flow_ids})
        return self._progress

    async def read_flows(self, ids: list[UUID] | None = None, names: list[str] | None = None) -> list[Flow]:
        self.read_flows_calls.append({"ids": ids, "names": names})
        return self._flows


class InMemoryFlowRunCounter:
    def __init__(self, count: int = 0) -> None:
        self._count = count
        self.count_calls: list[dict[str, Any]] = []

    async def count(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
    ) -> int:
        self.count_calls.append({"flow_filter": flow_filter, "flow_run_filter": flow_run_filter})
        return self._count


class InMemoryRelatedNodeEnricher:
    def __init__(self, related: RelatedNodesInfo | None = None) -> None:
        self._related = related or RelatedNodesInfo()
        self.enrich_calls: list[list[FlowRun]] = []

    async def enrich(self, flows: list[FlowRun]) -> RelatedNodesInfo:
        self.enrich_calls.append(flows)
        return self._related


def build_service(
    reader: InMemoryFlowRunReader | None = None,
    counter: InMemoryFlowRunCounter | None = None,
    enricher: InMemoryRelatedNodeEnricher | None = None,
) -> PrefectTaskService:
    return PrefectTaskService(
        filter_builder=FlowRunFilterBuilder(),
        reader=reader or InMemoryFlowRunReader(),
        counter=counter or InMemoryFlowRunCounter(),
        enricher=enricher or InMemoryRelatedNodeEnricher(),
        tag_decoder=WorkflowTagDecoder(),
    )


def make_flow_run(name: str = "run", flow_id: UUID | None = None, branch: str | None = None) -> FlowRun:
    tags = [WorkflowTag.BRANCH.render(identifier=branch)] if branch else []
    return FlowRun(flow_id=flow_id or uuid4(), name=name, tags=tags)


class TestPrefectTaskService:
    async def test_count_only_does_not_read_runs(self) -> None:
        reader = InMemoryFlowRunReader(flow_runs=[make_flow_run()])
        counter = InMemoryFlowRunCounter(count=7)
        service = build_service(reader=reader, counter=counter)

        result = await service.query(
            criteria=FlowRunQueryCriteria(), options=FlowRunFetchOptions(include_count=True, include_runs=False)
        )

        assert result.count == 7
        assert result.runs == []
        assert len(counter.count_calls) == 1
        assert counter.count_calls[0]["flow_run_filter"] is not None
        assert reader.read_flow_runs_calls == []

    async def test_runs_without_extra_fields_skips_optional_fetches(self) -> None:
        flow_run = make_flow_run(name="my-run", branch="main")
        reader = InMemoryFlowRunReader(flow_runs=[flow_run])
        enricher = InMemoryRelatedNodeEnricher()
        service = build_service(reader=reader, enricher=enricher)

        result = await service.query(
            criteria=FlowRunQueryCriteria(limit=5, offset=2), options=FlowRunFetchOptions(include_runs=True)
        )

        assert result.count == 0
        assert len(result.runs) == 1
        enriched = result.runs[0]
        assert enriched.flow_run is flow_run
        assert enriched.branch == "main"
        assert enriched.logs == []
        assert enriched.progress is None
        assert enriched.workflow_name is None
        assert enriched.related_nodes == []

        assert reader.read_flow_runs_calls[0]["limit"] == 5
        assert reader.read_flow_runs_calls[0]["offset"] == 2
        assert reader.read_logs_calls == []
        assert reader.read_progress_calls == []
        assert reader.read_flows_calls == []
        assert enricher.enrich_calls == []

    async def test_logs_are_attached_when_requested(self) -> None:
        flow_run = make_flow_run()
        logs = FlowLogs()
        log = PrefectLog(
            name="task",
            level=20,
            message="hello",
            timestamp=DateTime.now(tz=UTC),
            flow_run_id=flow_run.id,
        )
        logs.logs[flow_run.id].append(log)
        reader = InMemoryFlowRunReader(flow_runs=[flow_run], logs=logs)
        service = build_service(reader=reader)

        result = await service.query(
            criteria=FlowRunQueryCriteria(),
            options=FlowRunFetchOptions(include_runs=True, include_logs=True, log_limit=5, log_offset=2),
        )

        assert result.runs[0].logs == [log]
        assert reader.read_logs_calls[0]["flow_ids"] == [flow_run.id]
        assert reader.read_logs_calls[0]["log_limit"] == 5
        assert reader.read_logs_calls[0]["log_offset"] == 2

    async def test_progress_is_attached_when_requested(self) -> None:
        flow_run = make_flow_run()
        progress = FlowProgress()
        progress.data[flow_run.id] = 0.42
        reader = InMemoryFlowRunReader(flow_runs=[flow_run], progress=progress)
        service = build_service(reader=reader)

        result = await service.query(
            criteria=FlowRunQueryCriteria(),
            options=FlowRunFetchOptions(include_runs=True, include_progress=True),
        )

        assert result.runs[0].progress == 0.42
        assert reader.read_progress_calls[0]["flow_ids"] == [flow_run.id]

    async def test_related_nodes_are_attached_when_requested(self) -> None:
        flow_run = make_flow_run()
        related = RelatedNodesInfo()
        related.add_nodes(flow_id=flow_run.id, node_ids=["node-1"])
        related.nodes["node-1"].kind = "TestThing"
        enricher = InMemoryRelatedNodeEnricher(related=related)
        reader = InMemoryFlowRunReader(flow_runs=[flow_run])
        service = build_service(reader=reader, enricher=enricher)

        result = await service.query(
            criteria=FlowRunQueryCriteria(),
            options=FlowRunFetchOptions(include_runs=True, include_related_nodes=True),
        )

        assert enricher.enrich_calls == [[flow_run]]
        nodes = result.runs[0].related_nodes
        assert len(nodes) == 1
        assert nodes[0].id == "node-1"
        assert nodes[0].kind == "TestThing"

    async def test_workflow_name_is_resolved_when_requested(self) -> None:
        flow_run = make_flow_run()
        workflow = Flow(id=flow_run.flow_id, name="my_workflow", labels={})
        reader = InMemoryFlowRunReader(flow_runs=[flow_run], flows=[workflow])
        service = build_service(reader=reader)

        result = await service.query(
            criteria=FlowRunQueryCriteria(),
            options=FlowRunFetchOptions(include_runs=True, include_workflow=True),
        )

        assert result.runs[0].workflow_name == "my_workflow"
        assert reader.read_flows_calls[0]["ids"] == [flow_run.flow_id]
