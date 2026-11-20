from datetime import timedelta

from prefect.server.events.filters import EventFilter, EventNameFilter, EventOrder
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.schemas import PrefectBaseModel
from pydantic import BaseModel, Field

MINIMUM_DEFAULT_RANGE = timedelta(days=180)
"""Prefect's own default range, which a query that sets no start reads at least."""


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


class InfrahubDatabaseVersion(PrefectBaseModel):
    type: str = Field(..., description="The type of database, for example postgresql or sqlite")
    version: str | None = Field(..., description="The version reported by the database server")


class InfrahubEventfilterInput(BaseModel):
    limit: int = Field(default=50)
    filter: InfrahubEventFilter = Field(default_factory=InfrahubEventFilter.default)
    offset: int | None = Field(default=None)
    include_total: bool = Field(
        default=True,
        description="When false, skip the unbounded count query and report a null total; the paged events are unaffected",
    )


def default_range(event_retention: timedelta) -> timedelta:
    """Return how far back from its end a query that sets no start reads: the event retention, and at least 180 days.

    The process that deletes old events can run with other settings than the process that serves the query, so the
    range does not depend on whether this process would delete them.
    """
    return max(event_retention, MINIMUM_DEFAULT_RANGE)
