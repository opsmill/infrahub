from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node
from prefect.client.schemas.objects import StateType

from infrahub.core.task.task import Task as TaskNode
from infrahub.graphql.types.task import TaskNodes
from infrahub.task_manager.task import PrefectTask
from infrahub.workflows.constants import WorkflowTag

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class Tasks(ObjectType):
    edges = List(TaskNodes)
    count = Int()

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        limit: int = 10,
        offset: int = 0,
        ids: list | None = None,
        branch: str | None = None,
        related_node__ids: list | None = None,
    ) -> dict[str, Any]:
        related_nodes = related_node__ids or []
        ids = ids or []
        return await Tasks.query(
            info=info, branch=branch, limit=limit, offset=offset, ids=ids, related_nodes=related_nodes
        )

    @staticmethod
    async def resolve_branch_status(
        root: dict,  # pylint: disable=unused-argument
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
        ids: list[str] | None = None,
        statuses: list[StateType] | None = None,
        tags: list[str] | None = None,
        branch: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        context: GraphqlContext = info.context
        fields = await extract_fields_first_node(info)

        # During the migration, query both Prefect and Infrahub to get the list of tasks
        if not branch:
            infrahub_tasks = await TaskNode.query(
                db=context.db, fields=fields, limit=limit, offset=offset, ids=ids, related_nodes=related_nodes
            )
        else:
            infrahub_tasks = {}

        prefect_tasks = await PrefectTask.query(
            db=context.db,
            fields=fields,
            branch=branch,
            statuses=statuses,
            tags=tags,
            related_nodes=related_nodes,
            limit=limit,
            offset=offset,
        )
        infrahub_count = infrahub_tasks.get("count", None)
        prefect_count = prefect_tasks.get("count", None)
        return {
            "count": (infrahub_count or 0) + (prefect_count or 0),
            "edges": infrahub_tasks.get("edges", []) + prefect_tasks.get("edges", []),
        }


Task = Field(
    Tasks,
    resolver=Tasks.resolve,
    limit=Int(required=False),
    offset=Int(required=False),
    related_node__ids=List(String),
    branch=String(required=False),
    ids=List(String),
)

TaskBranchStatus = Field(
    Tasks,
    resolver=Tasks.resolve_branch_status,
    branch=String(required=False),
    description="Return the list of all pending or running tasks that can modify the data, for a given branch",
)
