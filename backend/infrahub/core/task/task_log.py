from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field

from infrahub.core.constants import Severity  # noqa: TC001
from infrahub.core.node.standard import StandardNode
from infrahub.core.query.task_log import TaskLogNodeCreateQuery
from infrahub.core.timestamp import current_timestamp

if TYPE_CHECKING:
    from infrahub.core.query.standard_node import StandardNodeQuery


class TaskLog(StandardNode):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: str = Field(..., description="The message of the log entry.")
    severity: Severity = Field(..., description="Severity of the event")
    task_id: str = Field(..., description="The ID of the associated task")
    timestamp: str = Field(default_factory=current_timestamp, description="The time when this task was created")

    _exclude_attrs: list[str] = ["id", "uuid", "task_id", "_query"]
    _query: type[StandardNodeQuery] = TaskLogNodeCreateQuery
