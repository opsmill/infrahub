from prefect.client.orchestration import PrefectClient

from infrahub.database import InfrahubDatabase
from infrahub.workers.dependencies import get_cache

from .cache_key import FlowRunCountCacheKeyBuilder
from .count import FlowRunCounter, FlowRunCounterProtocol
from .enrichment import RelatedNodeEnricher, RelatedNodeEnricherProtocol
from .filters import FlowRunFilterBuilder
from .models import (
    EnrichedFlowRun,
    FlowLogs,
    FlowProgress,
    FlowRunFetchOptions,
    FlowRunQueryCriteria,
    FlowRunQueryResult,
    RelatedNodesInfo,
)
from .prefect_client import PrefectClientAdapter
from .reader import FlowRunReader, FlowRunReaderProtocol
from .tags import WorkflowTagDecoder


class PrefectTaskService:
    """Gather flow-run data from Prefect and the graph, returning transport-agnostic results."""

    def __init__(
        self,
        filter_builder: FlowRunFilterBuilder,
        reader: FlowRunReaderProtocol,
        counter: FlowRunCounterProtocol,
        enricher: RelatedNodeEnricherProtocol,
        tag_decoder: WorkflowTagDecoder,
    ) -> None:
        self.filter_builder = filter_builder
        self.reader = reader
        self.counter = counter
        self.enricher = enricher
        self.tag_decoder = tag_decoder

    async def query(self, criteria: FlowRunQueryCriteria, options: FlowRunFetchOptions) -> FlowRunQueryResult:
        result = FlowRunQueryResult()

        flow_filter = self.filter_builder.build_flow_filter(workflows=criteria.workflows)
        flow_run_filter = self.filter_builder.build_flow_run_filter(criteria=criteria)

        if options.include_count:
            result.count = await self.counter.count(flow_filter=flow_filter, flow_run_filter=flow_run_filter)

        if not options.include_runs:
            return result

        flows = await self.reader.read_flow_runs(
            flow_filter=flow_filter,
            flow_run_filter=flow_run_filter,
            limit=criteria.limit,
            offset=criteria.offset,
        )
        flow_ids = [flow.id for flow in flows]

        logs = FlowLogs()
        if options.include_logs:
            logs = await self.reader.read_logs(
                flow_ids=flow_ids, log_limit=options.log_limit, log_offset=options.log_offset
            )

        progress = FlowProgress()
        if options.include_progress:
            progress = await self.reader.read_progress(flow_ids=flow_ids)

        related_nodes = RelatedNodesInfo()
        if options.include_related_nodes:
            related_nodes = await self.enricher.enrich(flows=flows)

        workflow_names: dict = {}
        if options.include_workflow:
            unique_flow_ids = {flow.flow_id for flow in flows}
            workflow_names = {flow.id: flow.name for flow in await self.reader.read_flows(ids=list(unique_flow_ids))}

        result.runs = [
            EnrichedFlowRun(
                flow_run=flow,
                branch=self.tag_decoder.branch_name(flow),
                related_nodes=related_nodes.get_related_nodes(flow_id=flow.id),
                workflow_name=workflow_names.get(flow.flow_id),
                progress=progress.data.get(flow.id),
                logs=list(logs.logs.get(flow.id, [])),
            )
            for flow in flows
        ]

        return result


async def build_prefect_task_service(db: InfrahubDatabase, client: PrefectClient) -> PrefectTaskService:
    tag_decoder = WorkflowTagDecoder()
    cache = await get_cache()
    prefect = PrefectClientAdapter(client)
    return PrefectTaskService(
        filter_builder=FlowRunFilterBuilder(),
        reader=FlowRunReader(client=prefect),
        counter=FlowRunCounter(client=prefect, cache=cache, cache_key_builder=FlowRunCountCacheKeyBuilder()),
        enricher=RelatedNodeEnricher(db=db, tag_decoder=tag_decoder),
        tag_decoder=tag_decoder,
    )
