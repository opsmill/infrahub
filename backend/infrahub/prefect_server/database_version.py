from fastapi import APIRouter
from fastapi.param_functions import Depends
from prefect.server.database import PrefectDBInterface

from .database import get_prefect_database, read_database_version
from .models import InfrahubDatabaseVersion

router = APIRouter(prefix="/database", tags=["Infrahub"])


@router.get("/version")
async def get_database_version(
    db: PrefectDBInterface = Depends(get_prefect_database),  # noqa: B008
) -> InfrahubDatabaseVersion:
    async with db.session_context() as session:
        return await read_database_version(session=session)
