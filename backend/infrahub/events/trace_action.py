from datetime import datetime
from typing import ClassVar

from pydantic import Field

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class TraceSampleRatioUpdatedEvent(InfrahubEvent):
    """Event generated when an administrator sets or clears the temporary trace sampling ratio."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.trace.sample_ratio_updated"

    previous_ratio: float = Field(
        ..., description="Ratio in force on the process that handled the request, before the change"
    )
    new_ratio: float = Field(
        ..., description="Ratio in force after the change; the default ratio when the temporary ratio is cleared"
    )
    expires_at: datetime | None = Field(
        default=None, description="UTC time when the temporary ratio stops applying; empty when it is cleared"
    )
    cleared: bool = Field(..., description="Indicates if the administrator cleared the temporary ratio")

    def get_resource(self) -> dict[str, str]:
        return {"prefect.resource.id": f"{EVENT_NAMESPACE}.trace.sample_ratio"}
