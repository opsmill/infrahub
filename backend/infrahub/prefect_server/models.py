from datetime import timedelta

from prefect.server.events.filters import EventFilter, EventNameFilter, EventOrder
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.schemas import PrefectBaseModel
from prefect.settings import get_current_settings
from pydantic import BaseModel, Field

from .retention import deletes_old_events

MAXIMUM_RETENTION_SECONDS = 36_500 * 24 * 60 * 60
KEPT_EVENTS_READ_WINDOW = timedelta(days=180)


class InfrahubEventFilter(EventFilter):
    def set_prefix(self) -> None:
        if self.event:
            if self.event.prefix is not None and "infrahub." not in self.event.prefix:
                self.event.prefix.append("infrahub.")
        else:
            self.event = EventNameFilter(prefix=["infrahub."], name=[], exclude_prefix=None, exclude_name=None)

    @classmethod
    def default(cls) -> "InfrahubEventFilter":
        return cls(event=None, any_resource=None, resource=None, related=None, order=EventOrder.DESC)


class InfrahubEventPage(PrefectBaseModel):
    events: list[ReceivedEvent] = Field(..., description="The Events matching the query")
    total: int | None = Field(default=None, description="The total number of matching Events, when requested")


class InfrahubEventfilterInput(BaseModel):
    limit: int = Field(default=50)
    filter: InfrahubEventFilter = Field(default_factory=InfrahubEventFilter.default)
    offset: int | None = Field(default=None)
    include_total: bool = Field(
        default=True,
        description="When false, skip the unbounded count query and report a null total; the paged events are unaffected",
    )
    retention_seconds: int | None = Field(
        default=None,
        gt=0,
        le=MAXIMUM_RETENTION_SECONDS,
        description=(
            "Time window read back from the end of the filter when it sets no start; "
            "by default the task manager's event retention, "
            "or at least 180 days when the task manager does not delete old events"
        ),
    )

    @property
    def retention(self) -> timedelta:
        if self.retention_seconds is not None:
            return timedelta(seconds=self.retention_seconds)
        settings = get_current_settings()
        retention = settings.server.events.retention_period
        if deletes_old_events(vacuum=settings.server.services.db_vacuum):
            return retention
        # Events past the retention stay stored, so at least Prefect's default 180-day range is read.
        return max(retention, KEPT_EVENTS_READ_WINDOW)
