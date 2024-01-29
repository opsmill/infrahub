from __future__ import annotations

from typing import Optional

from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class LogTaskResult(InfrahubMessage):
    """Logs the result of a background task"""

    account_id: Optional[str] = Field(default=None, description="Indicates the user that requested the task")
    task_id: str = Field(..., description="The unique ID of the Task")
    title: str = Field(..., description="The title of the task")
    message: str = Field(None, description="The message of the log entry")
    related_node: str = Field(..., description="The ID of the node this task is related to")
    success: bool = Field(..., description="Indicates if the task was successful or not.")
    severity: str = Field(..., description="Log entry severity")
