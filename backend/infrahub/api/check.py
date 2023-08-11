import enum
from typing import List, Optional

from fastapi import APIRouter, Depends
from neo4j import AsyncSession
from pydantic import BaseModel

from infrahub.api.dependencies import get_branch_dep, get_current_user, get_session
from infrahub.core.branch import Branch

# pylint    : disable=too-many-branches

router = APIRouter(prefix="/check")


class CheckType(str, enum.Enum):
    DATA_INTEGRITY = "data-integrity"
    SCHEMA_INTEGRITY = "schema-integrity"
    REPOSITORY_INTEGRITY = "schema-integrity"


class CheckStatus(str, enum.Enum):
    PASSED = "pass"
    ERROR = "error"
    WARNING = "warning"


class CheckBase(BaseModel):
    check_type: CheckType
    status: CheckStatus = CheckStatus.WARNING
    message: Optional[str] = None


class DataIntegrityCheck(CheckBase):
    # identifier: str
    paths: List[str]


@router.get("/data")
async def get_check_data(
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    _: str = Depends(get_current_user),
) -> List[DataIntegrityCheck]:
    diff = await branch.diff(session=session, diff_from=time_from, diff_to=time_to, branch_only=False)
    conflicts = await diff.get_conflicts(session=session)

    response = []

    for conflict in conflicts:
        response.append(
            DataIntegrityCheck(check_type=CheckType.DATA_INTEGRITY, status=CheckStatus.ERROR, paths=[conflict.path])
        )

    return response
