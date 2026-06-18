from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull, ObjectType, String
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import StateType

from infrahub.core.constants import TaskConclusion
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types.task import TaskNodes, TaskState
from infrahub.task_manager.flow_run.constants import CONCLUSION_STATE_MAPPING, LOG_LEVEL_MAPPING
from infrahub.task_manager.flow_run.models import (
    EnrichedFlowRun,
    FlowRunFetchOptions,
    FlowRunQueryCriteria,
    FlowRunQueryResult,
)
from infrahub.task_manager.flow_run.service import build_prefect_task_service
from infrahub.utils import get_nested_dict
from infrahub.workflows.constants import WorkflowTag

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class FlowRunConnectionSerializer:
    """Render flow-run query results into the GraphQL connection shape."""

    def serialize(self, result: FlowRunQueryResult) -> dict[str, Any]:
        return {
            "count": result.count,
            "edges": [{"node": self._serialize_node(run)} for run in result.runs],
        }

    def _serialize_node(self, run: EnrichedFlowRun) -> dict[str, Any]:
        flow = run.flow_run
        related_node = run.related_nodes[0] if run.related_nodes else None
        logs = [
            {
                "node": {
                    "message": log.message,
                    "severity": LOG_LEVEL_MAPPING.get(log.level, "error"),
                    "timestamp": log.timestamp.isoformat(),
                }
            }
            for log in run.logs
        ]
        return {
            "title": flow.name,
            "conclusion": CONCLUSION_STATE_MAPPING.get(str(flow.state_name), TaskConclusion.UNKNOWN).value,
            "state": flow.state_type,
            "progress": run.progress,
            "parameters": flow.parameters,
            "branch": run.branch,
            "tags": flow.tags,
            "workflow": run.workflow_name,
            "related_node": related_node.id if related_node else None,
            "related_node_kind": related_node.kind if related_node else None,
            "related_nodes": [node.model_dump() for node in run.related_nodes],
            "created_at": flow.created.isoformat() if flow.created else None,
            "updated_at": flow.updated.isoformat() if flow.updated else None,
            "start_time": flow.start_time.isoformat() if flow.start_time else None,
            "id": flow.id,
            "logs": {"edges": logs, "count": len(logs)},
        }


def _build_fetch_options(fields: dict[str, Any], log_limit: int | None, log_offset: int | None) -> FlowRunFetchOptions:
    node_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node"]) or {}
    log_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node", "logs", "edges", "node"])
    return FlowRunFetchOptions(
        include_count="count" in fields,
        include_runs=bool(node_fields),
        include_logs=bool(log_fields),
        include_progress="progress" in node_fields,
        include_related_nodes=any(key in node_fields for key in ("related_nodes", "related_node", "related_node_kind")),
        include_workflow="workflow" in node_fields,
        log_limit=log_limit,
        log_offset=log_offset,
    )


class Tasks(ObjectType):
    edges = List(NonNull(TaskNodes), required=True)
    count = Int(required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        limit: int = 10,
        offset: int = 0,
        ids: list[str] | None = None,
        branch: str | None = None,
        state: list | None = None,
        workflow: list[str] | None = None,
        related_node__ids: list | None = None,
        q: str | None = None,
        log_limit: int | None = None,
        log_offset: int | None = None,
    ) -> dict[str, Any]:
        related_nodes = related_node__ids or []
        ids = ids or []
        return await Tasks.query(
            info=info,
            branch=branch,
            limit=limit,
            offset=offset,
            q=q,
            ids=ids,
            statuses=state,
            workflows=workflow,
            related_nodes=related_nodes,
            log_limit=log_limit,
            log_offset=log_offset,
        )

    @staticmethod
    async def resolve_branch_status(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        branch: str,
    ) -> dict[str, Any]:
        statuses: list[StateType] = [StateType.PENDING, StateType.RUNNING, StateType.CANCELLING, StateType.SCHEDULED]
        tags: list[str] = [WorkflowTag.DATABASE_CHANGE.render()]

        return await Tasks.query(info=info, branch=branch, statuses=statuses, tags=tags)

    @classmethod
    async def query(
        cls,
        info: GraphQLResolveInfo,
        related_nodes: list[str] | None = None,
        q: str | None = None,
        ids: list[str] | None = None,
        statuses: list[StateType] | None = None,
        workflows: list[str] | None = None,
        tags: list[str] | None = None,
        branch: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        log_limit: int | None = None,
        log_offset: int | None = None,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context
        fields = extract_graphql_fields(info=info)

        criteria = FlowRunQueryCriteria(
            q=q,
            ids=ids,
            related_nodes=related_nodes,
            statuses=statuses,
            workflows=workflows,
            tags=tags,
            branch=branch,
            limit=limit,
            offset=offset,
        )
        options = _build_fetch_options(fields=fields, log_limit=log_limit, log_offset=log_offset)

        async with get_client(sync_client=False) as client:
            service = await build_prefect_task_service(db=graphql_context.db, client=client)
            result = await service.query(criteria=criteria, options=options)
        return FlowRunConnectionSerializer().serialize(result=result)


Task = Field(
    Tasks,
    limit=Int(required=False),
    offset=Int(required=False),
    related_node__ids=List(String),
    branch=String(required=False),
    state=List(TaskState),
    workflow=List(String),
    ids=List(String),
    q=String(required=False),
    log_limit=Int(required=False),
    log_offset=Int(required=False),
    resolver=Tasks.resolve,
    required=True,
)

TaskBranchStatus = Field(
    Tasks,
    branch=String(required=False),
    description="Return the list of all pending or running tasks that can modify the data, for a given branch",
    resolver=Tasks.resolve_branch_status,
    required=True,
)
