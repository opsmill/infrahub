from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node
from prefect.client.schemas.objects import StateType

from infrahub.graphql.types.task import TaskNodes, TaskState
from infrahub.task_manager.task import PrefectTask
from infrahub.workflows.constants import WorkflowTag

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


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
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context
        fields = await extract_fields_first_node(info)

        prefect_tasks = await PrefectTask.query(
            db=graphql_context.db,
            fields=fields,
            q=q,
            ids=ids,
            branch=branch,
            statuses=statuses,
            workflows=workflows,
            tags=tags,
            related_nodes=related_nodes,
            limit=limit,
            offset=offset,
        )
        prefect_count = prefect_tasks.get("count", None)
        return {
            "count": prefect_count or 0,
            "edges": prefect_tasks.get("edges", []),
        }


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
