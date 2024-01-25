from typing import List, Optional, Type

from pydantic import ConfigDict, Field

from infrahub.core.constants import TaskConclusion
from infrahub.core.definitions import NodeInfo
from infrahub.core.node.standard import StandardNode
from infrahub.core.query.standard_node import StandardNodeQuery
from infrahub.core.query.task import TaskNodeCreateQuery
from infrahub.core.timestamp import current_timestamp


class Task(StandardNode):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: str
    conclusion: TaskConclusion
    account_id: Optional[str] = Field(default=None, description="The ID of the account that created this task")
    created_timestamp: str = Field(default_factory=current_timestamp, description="The time when this task was created")
    related_node: Optional[NodeInfo] = Field(default=None, description="The Infrahub node that this object refers to")

    _exclude_attrs: List[str] = ["id", "uuid", "account_id", "_query", "related_node"]
    _query: Type[StandardNodeQuery] = TaskNodeCreateQuery
