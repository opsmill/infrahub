from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request, Response

from infrahub import config, models
from infrahub.api.dependencies import get_access_token, get_db, get_refresh_token
from infrahub.api.event_builder import make_event_meta, make_login_event, make_logout_event
from infrahub.auth import (
    AccountSession,
    AuthType,
    authenticate_with_password,
    create_fresh_access_token,
    invalidate_refresh_token,
)
from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericAccount
from infrahub.events.account_action import AuthMethod
from infrahub.exceptions import NodeNotFoundError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

log = get_logger()
router = APIRouter(prefix="/auth")


@router.post("/login")
async def login_user(
    request: Request,
    credentials: models.PasswordCredential,
    response: Response,
    db: InfrahubDatabase = Depends(get_db),
) -> models.UserToken:
    auth_result = await authenticate_with_password(db=db, credentials=credentials)
    response.set_cookie(
        "access_token",
        auth_result.token.access_token,
        httponly=True,
        max_age=config.SETTINGS.security.access_token_lifetime,
    )
    response.set_cookie(
        "refresh_token",
        auth_result.token.refresh_token,
        httponly=True,
        max_age=config.SETTINGS.security.refresh_token_lifetime,
    )
    service: InfrahubServices = request.app.state.service
    session = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=auth_result.account_id)
    branch = await registry.get_branch(db=db)
    try:
        event = make_login_event(
            request=request,
            event_meta=await make_event_meta(account_session=session, branch=branch),
            auth_result=auth_result,
            auth_method=AuthMethod.PASSWORD,
        )
        await service.event.send(event=event)
    except Exception as ex:
        log.warning(f"Failed to emit login event for account_id={auth_result.account_id}: {str(ex)}")
    return auth_result.token


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
    request: Request,
    response: Response,
    db: InfrahubDatabase = Depends(get_db),
    user_session: AccountSession = Depends(get_access_token),
) -> None:
    invalidated = False
    if user_session.session_id:
        invalidated = await invalidate_refresh_token(db=db, token_id=user_session.session_id)

    if invalidated:
        try:
            account = await NodeManager.get_one(
                id=user_session.account_id, db=db, kind=CoreGenericAccount, raise_on_error=True
            )
        except NodeNotFoundError as err:
            delete_response_cookies(response=response)
            raise

        account_name = account.name.value
        session_id = user_session.session_id or ""
        service: InfrahubServices = request.app.state.service
        branch = await registry.get_branch(db=db)
        try:
            event = make_logout_event(
                request=request,
                event_meta=await make_event_meta(account_session=user_session, branch=branch),
                account_kind=account.get_kind(),
                account_id=user_session.account_id,
                account_name=account_name,
                session_id=session_id,
            )
            await service.event.send(event=event)
        except Exception as ex:
            log.warning(f"Failed to emit logout event for account_id={user_session.account_id}: {str(ex)}")

    delete_response_cookies(response=response)


def delete_response_cookies(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
