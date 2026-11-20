from fastapi import APIRouter
from fastapi.param_functions import Depends
from prefect.server.database import PrefectDBInterface, provide_database_interface
from sqlalchemy import text

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
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            # After five executions of a prepared statement Postgres may switch it to a
            # generic plan chosen without seeing the parameter values; for these event
            # filters that plan degrades to a quadratic join that stalls for tens of
            # seconds. Force per-execution planning for this transaction only, so the
            # rest of the Prefect server keeps its prepared-statement plan caching.
            await session.execute(text("SET LOCAL plan_cache_mode = force_custom_plan"))
        events, total = await query_events(
            session=session,
            filter=event_filter.filter,
            page_size=event_filter.limit,
            offset=event_filter.offset,
            include_total=event_filter.include_total,
        )

        return InfrahubEventPage(
            events=events,
            total=total,
        )
