from fastapi import APIRouter, Depends
from neo4j import AsyncSession

from infrahub import models
from infrahub.api.dependencies import get_refresh_token, get_session
from infrahub.auth import authenticate_with_password, create_fresh_access_token

router = APIRouter(prefix="/auth")


@router.post("/login")
async def login_user(
    credentials: models.PasswordCredential,
    session: AsyncSession = Depends(get_session),
) -> models.UserToken:
    return await authenticate_with_password(session=session, credentials=credentials)


@router.post("/refresh")
async def refresh_jwt_token(
    session: AsyncSession = Depends(get_session),
    refresh_token: models.RefreshTokenData = Depends(get_refresh_token),
) -> models.AccessTokenResponse:
    return await create_fresh_access_token(session=session, refresh_data=refresh_token)
