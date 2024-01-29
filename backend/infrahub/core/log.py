from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Type

from pydantic import ConfigDict, Field

from infrahub.core.constants import Severity  # noqa: TCH001
from infrahub.core.node.standard import StandardNode
from infrahub.core.query.log import LogNodeCreateQuery, LogNodeQuery
from infrahub.core.timestamp import current_timestamp

if TYPE_CHECKING:
    from infrahub.core.query.standard_node import StandardNodeQuery
    from infrahub.database import InfrahubDatabase


class Log(StandardNode):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: str = Field(..., description="The message of the log entry.")
    severity: Severity = Field(..., description="Severity of the event")
    task_id: str = Field(..., description="The ID of the account that created this task")
    timestamp: str = Field(default_factory=current_timestamp, description="The time when this task was created")

    _exclude_attrs: List[str] = [
        "id",
        "uuid",
        "task_id",
        "_query",
    ]
    _query: Type[StandardNodeQuery] = LogNodeCreateQuery

    @classmethod
    async def query(cls, db: InfrahubDatabase, page_size: int = 10, cursor: str = "") -> Dict[str, Any]:
        query = await LogNodeQuery.init(db=db, page_size=page_size, cursor=cursor)
        await query.execute(db=db)
        nodes = []
        for result in query.get_results():
            task = result.get("t")
            related_node = result.get("rn")
            log = cls.from_db(node=result.get_node("n"), extras={"task_id": task.get("uuid")})

            nodes.append(
                {
                    "message": log.message,
                    "related_node": related_node.get("uuid"),
                    "related_node_kind": related_node.get("kind"),
                    "severity": log.severity,
                    "timestamp": log.timestamp,
                    "task_id": task.get("uuid"),
                }
            )

        return {"has_next": query.has_next, "next_cursor": query.next_cursor, "edges": {"node": nodes}}
