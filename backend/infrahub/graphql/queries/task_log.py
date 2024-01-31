from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from graphene import Boolean, Field, Int, ObjectType, String

from infrahub.core.task_log import TaskLog as TaskLogNode
from infrahub.graphql.types import TaskLogNodes

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.database import InfrahubDatabase


class TaskLogs(ObjectType):
    has_next = Boolean(required=True)
    next_cursor = String(required=True)
    edges = Field(TaskLogNodes)

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        page_size: int = 10,
        cursor: str = "",
    ) -> Dict[str, Any]:
        return await TaskLogs.query(
            info=info,
            page_size=page_size,
            cursor=cursor,
        )

    @classmethod
    async def query(
        cls,
        info: GraphQLResolveInfo,
        page_size: int,
        cursor: str,
    ) -> Dict[str, Any]:
        db: InfrahubDatabase = info.context.get("infrahub_database")

        return await TaskLogNode.query(db=db, page_size=page_size, cursor=cursor)


TaskLog = Field(TaskLogs, resolver=TaskLogs.resolve, page_size=Int(required=False), cursor=String(required=False))
