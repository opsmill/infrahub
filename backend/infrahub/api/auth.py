from typing import Optional

from fastapi import APIRouter, Depends
from neo4j import AsyncSession

from infrahub import models
from infrahub.api.dependencies import get_session
from infrahub.auth import authenticate_with_password

router = APIRouter(prefix="/auth")


@router.post("/login")
async def login_user(
    credentials: models.PasswordCredential,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
) -> models.UserToken:
    return await authenticate_with_password(session=session, credentials=credentials, branch=branch)
