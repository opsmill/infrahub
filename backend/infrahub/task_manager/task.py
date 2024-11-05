import uuid
from typing import Any
from uuid import UUID

from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas import FlowRun
from prefect.client.schemas.filters import (
    ArtifactFilter,
    ArtifactFilterType,
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateType,
    FlowRunFilterTags,
    LogFilter,
    LogFilterFlowRunId,
)
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.sorting import (
    FlowRunSort,
)

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
        flow_run_filter: FlowRunFilter | None = None,
    ) -> int:
        """
        Method to count the number of flow runs based on a flow_run_filter.
        The format of the body is the same as the one generated in read_flow_runs
        """
        body = {"flow_runs": (flow_run_filter.model_dump(mode="json", exclude_unset=True) if flow_run_filter else None)}

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
            related_nodes.id[flow.id] = related_node_ids[0]

        if unique_related_node_ids := related_nodes.get_unique_related_node_ids():
            query = await NodeGetKindQuery.init(db=db, ids=unique_related_node_ids)
            await query.execute(db=db)
            unique_related_node_ids_kind = await query.get_node_kind_map()

            for flow_id, node_id in related_nodes.id.items():
                related_nodes.kind[flow_id] = unique_related_node_ids_kind.get(node_id, None)

        return related_nodes

    @classmethod
    async def _get_logs(cls, client: PrefectClient, flow_ids: list[UUID]) -> FlowLogs:
        logs_flow = FlowLogs()
        all_logs = await client.read_logs(log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=flow_ids)))
        for flow_log in all_logs:
            if flow_log.flow_run_id:
                logs_flow.logs[flow_log.flow_run_id].append(flow_log)

        return logs_flow

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
    async def query(
        cls,
        db: InfrahubDatabase,
        fields: dict[str, Any],
        ids: list[str] | None = None,
        related_nodes: list[str] | None = None,
        statuses: list[StateType] | None = None,
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
        related_nodes_info = RelatedNodesInfo()

        async with get_client(sync_client=False) as client:
            filter_tags = [TAG_NAMESPACE]

            if tags:
                filter_tags.extend(tags)
            if branch:
                filter_tags.append(WorkflowTag.BRANCH.render(identifier=branch))
            # We only support one related node for now, need to investigate HOW (and IF) we can support more
            if related_nodes:
                filter_tags.append(WorkflowTag.RELATED_NODE.render(identifier=related_nodes[0]))

            flow_run_filters = FlowRunFilter(
                tags=FlowRunFilterTags(all_=filter_tags),
            )

            if ids:
                flow_run_filters.id = FlowRunFilterId(any_=[uuid.UUID(id) for id in ids])

            if statuses:
                flow_run_filters.state = FlowRunFilterState(type=FlowRunFilterStateType(any_=statuses))

            if "count" in fields:
                count = await cls.count_flow_runs(client=client, flow_run_filter=flow_run_filters)

            if node_fields:
                flows = await client.read_flow_runs(
                    flow_run_filter=flow_run_filters,
                    limit=limit,
                    offset=offset,
                    sort=FlowRunSort.START_TIME_DESC,
                )
                if log_fields:
                    logs_flow = await cls._get_logs(client=client, flow_ids=[flow.id for flow in flows])

                if "progress" in node_fields:
                    progress_flow = await cls._get_progress(client=client, flow_ids=[flow.id for flow in flows])

                if "related_node" in node_fields or "related_node_kind" in node_fields:
                    related_nodes_info = await cls._get_related_nodes(db=db, flows=flows)

                for flow in flows:
                    logs = []

                    if log_fields:
                        logs = logs_flow.to_graphql(flow_id=flow.id)

                    nodes.append(
                        {
                            "node": {
                                "title": flow.name,
                                "conclusion": CONCLUSION_STATE_MAPPING[flow.state_name].value,
                                "state": flow.state_type,
                                "progress": progress_flow.data.get(flow.id, None),
                                "parameters": flow.parameters,
                                "branch": cls._extract_branch_name(flow=flow),
                                "tags": flow.tags,
                                "related_node": related_nodes_info.id.get(flow.id, None),
                                "related_node_kind": related_nodes_info.kind.get(flow.id, None),
                                "created_at": flow.created.to_iso8601_string(),
                                "updated_at": flow.updated.to_iso8601_string(),
                                "start_time": flow.start_time.to_iso8601_string() if flow.start_time else None,
                                "id": flow.id,
                                "logs": {"edges": logs},
                            }
                        }
                    )

        return {"count": count or 0, "edges": nodes}
