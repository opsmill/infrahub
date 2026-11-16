from fastapi import APIRouter
from fastapi.param_functions import Depends
from prefect.server.database import PrefectDBInterface, provide_database_interface

from .database import read_database_version
from .models import InfrahubDatabaseVersion

router = APIRouter(prefix="/database", tags=["Infrahub"])


@router.get("/version")
async def get_database_version(
    db: PrefectDBInterface = Depends(provide_database_interface),  # noqa: B008
) -> InfrahubDatabaseVersion:
    async with db.session_context() as session:
        return await read_database_version(session=session)
