from fastapi import APIRouter
from fastapi.param_functions import Depends
from prefect.server.database import PrefectDBInterface, provide_database_interface

from .database import query_events
from .models import InfrahubEventfilterInput, InfrahubEventPage

router = APIRouter(prefix="/events", tags=["Infrahub"])


@router.post(
    "/filter",
)
async def read_events(
    event_filter: InfrahubEventfilterInput,
    db: PrefectDBInterface = Depends(provide_database_interface),  # noqa: B008
) -> InfrahubEventPage:
    event_filter.filter.set_prefix()

    async with db.session_context() as session:
        events, total = await query_events(
            session=session, filter=event_filter.filter, page_size=event_filter.limit, offset=event_filter.offset
        )

        return InfrahubEventPage(
            events=events,
            total=total,
        )
