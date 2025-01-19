import uuid
from typing import Any
from uuid import UUID

from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.filters import (
    ArtifactFilter,
    ArtifactFilterType,
    FlowFilter,
    FlowFilterId,
    FlowFilterName,
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterName,
    FlowRunFilterState,
    FlowRunFilterStateType,
    FlowRunFilterTags,
    LogFilter,
    LogFilterFlowRunId,
)
from prefect.client.schemas.objects import Flow, FlowRun, StateType
from prefect.client.schemas.sorting import (
    FlowRunSort,
)

from infrahub.core.constants import TaskConclusion
from infrahub.core.query.node import NodeGetKindQuery
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger
from infrahub.utils import get_nested_dict
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag

from .constants import CONCLUSION_STATE_MAPPING
from .models import FlowLogs, FlowProgress, RelatedNodesInfo

log = get_logger()


class PrefectTask:
    @classmethod
    async def count_flow_runs(
        cls,
        client: PrefectClient,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
    ) -> int:
        """
        Method to count the number of flow runs based on a flow_run_filter.
        The format of the body is the same as the one generated in read_flow_runs
        """
        body = {
            "flows": flow_filter.model_dump(mode="json") if flow_filter else None,
            "flow_runs": (flow_run_filter.model_dump(mode="json", exclude_unset=True) if flow_run_filter else None),
        }

        response = await client._client.post("/flow_runs/count", json=body)
        response.raise_for_status()
        return response.json()

    @classmethod
    async def _get_related_nodes(cls, db: InfrahubDatabase, flows: list[FlowRun]) -> RelatedNodesInfo:
        related_nodes = RelatedNodesInfo()

        # Extract all related nodes ID from tags
        for flow in flows:
            related_node_tag_prefix = WorkflowTag.RELATED_NODE.render(identifier="")
            related_node_ids = [
                tag.replace(related_node_tag_prefix, "") for tag in flow.tags if tag.startswith(related_node_tag_prefix)
            ]
            if not related_node_ids:
                continue
            related_nodes.add_nodes(flow_id=flow.id, node_ids=related_node_ids)

        if unique_related_node_ids := related_nodes.get_unique_related_node_ids():
            query = await NodeGetKindQuery.init(db=db, ids=unique_related_node_ids)
            await query.execute(db=db)
            unique_related_node_ids_kind = await query.get_node_kind_map()

            for node_id, node_kind in unique_related_node_ids_kind.items():
                if node_id in related_nodes.nodes:
                    related_nodes.nodes[node_id].kind = node_kind

        return related_nodes

    @classmethod
    async def _get_logs(cls, client: PrefectClient, flow_ids: list[UUID]) -> FlowLogs:
        logs_flow = FlowLogs()
        all_logs = await client.read_logs(log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=flow_ids)))
        for flow_log in all_logs:
            if flow_log.flow_run_id and flow_log.message not in ["Finished in state Completed()"]:
                logs_flow.logs[flow_log.flow_run_id].append(flow_log)

        return logs_flow

    @classmethod
    async def _get_flows(
        cls, client: PrefectClient, ids: list[UUID] | None = None, names: list[str] | None = None
    ) -> list[Flow]:
        if not names and not ids:
            return await client.read_flows()

        flow_filter = FlowFilter()
        flow_filter.name = FlowFilterName(any_=names) if names else None
        flow_filter.id = FlowFilterId(any_=ids) if ids else None
        return await client.read_flows(flow_filter=flow_filter)

    @classmethod
    async def _get_progress(cls, client: PrefectClient, flow_ids: list[UUID]) -> FlowProgress:
        artifacts = await client.read_artifacts(
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

    @classmethod
    async def _extract_branch_name(cls, flow: FlowRun) -> str | None:
        branch_name = [
            tag.replace(WorkflowTag.BRANCH.render(identifier=""), "")
            for tag in flow.tags
            if tag.startswith(WorkflowTag.BRANCH.render(identifier=""))
        ]

        return branch_name[0] if branch_name else None

    @classmethod
    def _generate_flow_filter(cls, workflows: list[str] | None = None) -> FlowFilter:
        flow_filter = FlowFilter()
        if workflows:
            flow_filter.name = FlowFilterName(any_=workflows)
        return flow_filter

    @classmethod
    def _generate_flow_run_filter(
        cls,
        q: str | None = None,
        ids: list[str] | None = None,
        related_nodes: list[str] | None = None,
        statuses: list[StateType] | None = None,
        tags: list[str] | None = None,
        branch: str | None = None,
    ) -> FlowRunFilter:
        filter_tags = [TAG_NAMESPACE]

        if tags:
            filter_tags.extend(tags)
        if branch:
            filter_tags.append(WorkflowTag.BRANCH.render(identifier=branch))
        # We only support one related node for now, need to investigate HOW (and IF) we can support more

        if related_nodes:
            filter_tags.append(WorkflowTag.RELATED_NODE.render(identifier=related_nodes[0]))

        flow_run_filter = FlowRunFilter(
            tags=FlowRunFilterTags(all_=filter_tags),
        )
        if ids:
            flow_run_filter.id = FlowRunFilterId(any_=[uuid.UUID(id) for id in ids])

        if statuses:
            flow_run_filter.state = FlowRunFilterState(type=FlowRunFilterStateType(any_=statuses))

        if q:
            flow_run_filter.name = FlowRunFilterName(like_=q)

        return flow_run_filter

    @classmethod
    async def query(
        cls,
        db: InfrahubDatabase,
        fields: dict[str, Any],
        q: str | None = None,
        ids: list[str] | None = None,
        related_nodes: list[str] | None = None,
        statuses: list[StateType] | None = None,
        workflows: list[str] | None = None,
        tags: list[str] | None = None,
        branch: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        nodes: list[dict] = []
        count = None

        node_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node"])
        log_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node", "logs", "edges", "node"])
        logs_flow = FlowLogs()
        progress_flow = FlowProgress()
        workflow_names: dict[UUID, str] = {}
        related_nodes_info = RelatedNodesInfo()

        async with get_client(sync_client=False) as client:
            flow_filter = cls._generate_flow_filter(workflows=workflows)
            flow_run_filter = cls._generate_flow_run_filter(
                q=q, ids=ids, related_nodes=related_nodes, statuses=statuses, tags=tags, branch=branch
            )

            if "count" in fields:
                count = await cls.count_flow_runs(
                    client=client, flow_filter=flow_filter, flow_run_filter=flow_run_filter
                )

            if node_fields:
                flows = await client.read_flow_runs(
                    flow_filter=flow_filter,
                    flow_run_filter=flow_run_filter,
                    limit=limit,
                    offset=offset or 0,
                    sort=FlowRunSort.START_TIME_DESC,
                )
                if log_fields:
                    logs_flow = await cls._get_logs(client=client, flow_ids=[flow.id for flow in flows])

                if "progress" in node_fields:
                    progress_flow = await cls._get_progress(client=client, flow_ids=[flow.id for flow in flows])

                if (
                    "related_nodes" in node_fields
                    or "related_node" in node_fields
                    or "related_node_kind" in node_fields
                ):
                    related_nodes_info = await cls._get_related_nodes(db=db, flows=flows)

                if "workflow" in node_fields:
                    unique_flow_ids = {flow.flow_id for flow in flows}
                    workflow_names = {
                        flow.id: flow.name for flow in await cls._get_flows(client=client, ids=list(unique_flow_ids))
                    }

                for flow in flows:
                    logs = []

                    if log_fields:
                        logs = logs_flow.to_graphql(flow_id=flow.id)

                    related_node = related_nodes_info.get_first_related_node(flow_id=flow.id)

                    nodes.append(
                        {
                            "node": {
                                "title": flow.name,
                                "conclusion": CONCLUSION_STATE_MAPPING.get(
                                    str(flow.state_name), TaskConclusion.UNKNOWN
                                ).value,
                                "state": flow.state_type,
                                "progress": progress_flow.data.get(flow.id, None),
                                "parameters": flow.parameters,
                                "branch": await cls._extract_branch_name(flow=flow),
                                "tags": flow.tags,
                                "workflow": workflow_names.get(flow.flow_id, None),
                                "related_node": related_node.id if related_node else None,
                                "related_node_kind": related_node.kind if related_node else None,
                                "related_nodes": related_nodes_info.get_related_nodes_as_dict(flow_id=flow.id),
                                "created_at": flow.created.to_iso8601_string(),  # type: ignore
                                "updated_at": flow.updated.to_iso8601_string(),  # type: ignore
                                "start_time": flow.start_time.to_iso8601_string() if flow.start_time else None,
                                "id": flow.id,
                                "logs": {"edges": logs},
                            }
                        }
                    )

        return {"count": count or 0, "edges": nodes}
