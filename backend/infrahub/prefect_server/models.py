from typing import TYPE_CHECKING, Sequence, cast

from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.events.filters import EventFilter, EventNameFilter, EventOrder, EventRelatedFilter
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.schemas import PrefectBaseModel
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sqlalchemy.sql.expression import ColumnExpressionArgument


class InfrahubEventFilter(EventFilter):
    matching_related: list[EventRelatedFilter] = Field(default_factory=list)

    def set_prefix(self) -> None:
        if self.event:
            if self.event.prefix is not None and "infrahub." not in self.event.prefix:
                self.event.prefix.append("infrahub.")
        else:
            self.event = EventNameFilter(prefix=["infrahub."], name=[], exclude_prefix=None, exclude_name=None)

    @db_injector
    def build_where_clauses(self, db: PrefectDBInterface) -> Sequence["ColumnExpressionArgument[bool]"]:
        result = cast(list["ColumnExpressionArgument[bool]"], super().build_where_clauses())
        top_level_filter = self._scoped_event_resources(db)
        for matching_related in self.matching_related:
            matching_related._top_level_filter = top_level_filter
            result.extend(matching_related.build_where_clauses())

        return result

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
