from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from graphene import Boolean, Field, Int, List, ObjectType, String

from infrahub.core.log import Log as LogObj

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.database import InfrahubDatabase


class LogEntry(ObjectType):
    message = String(required=True)
    related_node = String(required=True)
    related_node_kind = String(required=True)
    severity = String(required=True)
    task_id = String(required=True)
    timestamp = String(required=True)


class LogNode(ObjectType):
    node = List(LogEntry)


class Logs(ObjectType):
    has_next = Boolean(required=True)
    next_cursor = String(required=True)
    edges = Field(LogNode)

    @staticmethod
    async def resolve(
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        page_size: int = 10,
        cursor: str = "",
    ) -> Dict[str, Any]:
        return await Logs.query(
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

        return await LogObj.query(db=db, page_size=page_size, cursor=cursor)


Log = Field(Logs, resolver=Logs.resolve, page_size=Int(required=False), cursor=String(required=False))
