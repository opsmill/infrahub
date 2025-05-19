from prefect.server.events.filters import EventFilter, EventNameFilter, EventOrder
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.schemas import PrefectBaseModel
from pydantic import BaseModel, Field


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
    total: int = Field(..., description="The total number of matching Events")


class InfrahubEventfilterInput(BaseModel):
    limit: int = Field(default=50)
    filter: InfrahubEventFilter = Field(default_factory=InfrahubEventFilter.default)
    offset: int | None = Field(default=None)
