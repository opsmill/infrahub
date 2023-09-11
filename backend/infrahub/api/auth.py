from fastapi import APIRouter, Depends, Response
from neo4j import AsyncSession

from infrahub import models
from infrahub.api.dependencies import get_access_token, get_refresh_token, get_session
from infrahub.auth import (
    AccountSession,
    authenticate_with_password,
    create_fresh_access_token,
    invalidate_refresh_token,
)

router = APIRouter(prefix="/auth")


@router.post("/login")
async def login_user(
    credentials: models.PasswordCredential,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> models.UserToken:
    token = await authenticate_with_password(session=session, credentials=credentials)
    response.set_cookie("access_token", token.access_token, httponly=True)
    response.set_cookie("refresh_token", token.refresh_token, httponly=True)
    return token


@router.post("/refresh")
async def refresh_jwt_token(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: models.RefreshTokenData = Depends(get_refresh_token),
) -> models.AccessTokenResponse:
    token = await create_fresh_access_token(session=session, refresh_data=refresh_token)
    response.set_cookie("access_token", token.access_token, httponly=True)

    return token


@router.post("/logout")
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_session),
    user_session: AccountSession = Depends(get_access_token),
) -> None:
    if user_session.session_id:
        await invalidate_refresh_token(session=session, token_id=user_session.session_id)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
