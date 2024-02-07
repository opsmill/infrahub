from typing import Any, Dict, List, Optional, Type

from pydantic import ConfigDict, Field

from infrahub.core.constants import TaskConclusion
from infrahub.core.definitions import NodeInfo
from infrahub.core.node.standard import StandardNode
from infrahub.core.query.standard_node import StandardNodeQuery
from infrahub.core.query.task import TaskNodeCreateQuery, TaskNodeQuery, TaskNodeQueryWithLogs
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase
from infrahub.utils import get_nested_dict

from .task_log import TaskLog


class Task(StandardNode):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str
    conclusion: TaskConclusion
    account_id: Optional[str] = Field(default=None, description="The ID of the account that created this task")
    created_at: str = Field(default_factory=current_timestamp, description="The time when this task was created")
    updated_at: str = Field(default_factory=current_timestamp, description="The time when this task was last updated")
    related_node: Optional[NodeInfo] = Field(default=None, description="The Infrahub node that this object refers to")

    _exclude_attrs: List[str] = ["id", "uuid", "account_id", "_query", "related_node"]
    _query: Type[StandardNodeQuery] = TaskNodeCreateQuery

    @property
    def related(self) -> NodeInfo:
        if self.related_node:
            return self.related_node
        raise ValueError("The related_node field has not been populated")

    @classmethod
    async def query(
        cls, db: InfrahubDatabase, fields: Dict[str, Any], limit: int, offset: int, related_nodes: List[str]
    ) -> Dict[str, Any]:
        log_fields = get_nested_dict(nested_dict=fields, keys=["edges", "node", "logs", "edges", "node"])
        count = None
        if "count" in fields:
            query = await TaskNodeQuery.init(db=db, related_nodes=related_nodes)
            count = await query.count(db=db)

        if log_fields:
            query = await TaskNodeQueryWithLogs.init(db=db, limit=limit, offset=offset, related_nodes=related_nodes)
            await query.execute(db=db)
        else:
            query = await TaskNodeQuery.init(db=db, limit=limit, offset=offset, related_nodes=related_nodes)
            await query.execute(db=db)

        nodes: list[dict] = []
        for result in query.get_results():
            related_node = result.get("rn")
            task_result = result.get_node("n")
            logs = []
            if log_fields:
                logs_results = result.get_node_collection("logs")
                logs = [
                    {
                        "node": await TaskLog.from_db(result, extras={"task_id": task_result.get("uuid")}).to_graphql(
                            fields=log_fields
                        )
                    }
                    for result in logs_results
                ]

            task = cls.from_db(task_result)
            nodes.append(
                {
                    "node": {
                        "title": task.title,
                        "conclusion": task.conclusion,
                        "related_node": related_node.get("uuid"),
                        "related_node_kind": related_node.get("kind"),
                        "created_at": task.created_at,
                        "updated_at": task.updated_at,
                        "id": task_result.get("uuid"),
                        "logs": {"edges": logs},
                    }
                }
            )

        return {"count": count, "edges": nodes}
