from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response

from infrahub import config, models
from infrahub.api.dependencies import get_access_token, get_db, get_refresh_token
from infrahub.auth import (
    AccountSession,
    authenticate_with_password,
    create_fresh_access_token,
    invalidate_refresh_token,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

router = APIRouter(prefix="/auth")


@router.post("/login")
async def login_user(
    credentials: models.PasswordCredential, response: Response, db: InfrahubDatabase = Depends(get_db)
) -> models.UserToken:
    token = await authenticate_with_password(db=db, credentials=credentials)
    response.set_cookie(
        "access_token", token.access_token, httponly=True, max_age=config.SETTINGS.security.access_token_lifetime
    )
    response.set_cookie(
        "refresh_token", token.refresh_token, httponly=True, max_age=config.SETTINGS.security.refresh_token_lifetime
    )
    return token


@router.post("/refresh")
async def refresh_jwt_token(
    response: Response,
    db: InfrahubDatabase = Depends(get_db),
    refresh_token: models.RefreshTokenData = Depends(get_refresh_token),
) -> models.AccessTokenResponse:
    token = await create_fresh_access_token(db=db, refresh_data=refresh_token)
    response.set_cookie(
        "access_token", token.access_token, httponly=True, max_age=config.SETTINGS.security.access_token_lifetime
    )

    return token


@router.post("/logout")
async def logout(
    response: Response, db: InfrahubDatabase = Depends(get_db), user_session: AccountSession = Depends(get_access_token)
) -> None:
    if user_session.session_id:
        await invalidate_refresh_token(db=db, token_id=user_session.session_id)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
