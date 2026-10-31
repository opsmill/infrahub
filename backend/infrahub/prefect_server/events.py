from fastapi import APIRouter
from fastapi.param_functions import Depends
from prefect.server.database import PrefectDBInterface, provide_database_interface

from .database import query_events
from .models import InfrahubEventfilterInput, InfrahubEventPage

router = APIRouter(prefix="/events", tags=["Infrahub"])


async def get_prefect_database() -> PrefectDBInterface:
    """Resolve the database interface on the event loop, since FastAPI runs a sync dependency in a worker thread."""
    return provide_database_interface()


@router.post(
    "/filter",
)
async def read_events(
    event_filter: InfrahubEventfilterInput,
    db: PrefectDBInterface = Depends(get_prefect_database),  # noqa: B008
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
