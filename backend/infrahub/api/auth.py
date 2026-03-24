from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request, Response

from infrahub import config, models
from infrahub.api.dependencies import get_access_token, get_db, get_permission_manager, get_refresh_token
from infrahub.auth import (
    AccountSession,
    AuthType,
    authenticate_with_password,
    create_fresh_access_token,
    invalidate_refresh_token,
)
from infrahub.context import InfrahubContext
from infrahub.core.constants import GlobalPermissions
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericAccount, InternalRefreshToken
from infrahub.core.registry import registry
from infrahub.events.account_action import AccountLoggedInEvent, AccountLoggedOutEvent, AuthMethod, LogoutType
from infrahub.events.models import EventMeta
from infrahub.exceptions import NodeNotFoundError
from infrahub.log import get_logger
from infrahub.permissions import PermissionManager, define_global_permission_from_branch

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import InfrahubEvent
    from infrahub.services import InfrahubServices

log = get_logger()
router = APIRouter(prefix="/auth")


async def emit_auth_event(
    request: Request,
    db: InfrahubDatabase,
    account_id: str,
    account_session: AccountSession,
    event_factory: Callable[[EventMeta], InfrahubEvent],
) -> None:
    service: InfrahubServices = request.app.state.service
    branch = await registry.get_branch(db=db)
    meta = EventMeta(
        branch=branch,
        context=InfrahubContext.init(branch=branch, account=account_session),
        account_id=account_id,
    )
    await service.event.send(event=event_factory(meta))


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
    try:
        session = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=auth_result.account_id)
        await emit_auth_event(
            request=request,
            db=db,
            account_id=auth_result.account_id,
            account_session=session,
            event_factory=lambda meta: AccountLoggedInEvent(
                meta=meta,
                account_id=auth_result.account_id,
                account_name=auth_result.account_name,
                account_type=auth_result.account_type,
                auth_method=AuthMethod.PASSWORD,
                session_id=str(auth_result.session_id),
                groups=auth_result.groups,
                roles=auth_result.roles,
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            ),
        )
    except Exception:
        log.warning("Failed to emit login event")
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
    if user_session.session_id:
        await invalidate_refresh_token(db=db, token_id=user_session.session_id)

    try:
        account = await NodeManager.get_one(id=user_session.account_id, db=db, kind=CoreGenericAccount)
        account_name = account.name.value if account else user_session.account_id
        session_id = user_session.session_id or ""
        await emit_auth_event(
            request=request,
            db=db,
            account_id=user_session.account_id,
            account_session=user_session,
            event_factory=lambda meta: AccountLoggedOutEvent(
                meta=meta,
                account_id=user_session.account_id,
                account_name=account_name,
                session_id=session_id,
                logout_type=LogoutType.USER_INITIATED,
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            ),
        )
    except Exception:
        log.warning("Failed to emit logout event")

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/sessions/{session_id}/invalidate")
async def invalidate_session(
    request: Request,
    session_id: str,
    db: InfrahubDatabase = Depends(get_db),
    permission_manager: PermissionManager = Depends(get_permission_manager),
) -> None:
    permission_manager.raise_for_permission(
        permission=define_global_permission_from_branch(
            permission=GlobalPermissions.MANAGE_ACCOUNTS,
            branch_name=registry.default_branch,
        )
    )

    refresh_token_node = await NodeManager.get_one(id=session_id, db=db, kind=InternalRefreshToken)
    if not refresh_token_node:
        raise NodeNotFoundError(node_type="InternalRefreshToken", identifier=session_id)

    account_peers = await refresh_token_node.account.get_peers(db=db, peer_type=CoreGenericAccount)
    account = next(iter(account_peers.values()), None) if account_peers else None
    account_id = account.id if account else session_id
    account_name = account.name.value if account and hasattr(account, "name") else account_id

    await invalidate_refresh_token(db=db, token_id=session_id)

    try:
        admin_session = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=account_id)
        await emit_auth_event(
            request=request,
            db=db,
            account_id=account_id,
            account_session=admin_session,
            event_factory=lambda meta: AccountLoggedOutEvent(
                meta=meta,
                account_id=account_id,
                account_name=account_name,
                session_id=session_id,
                logout_type=LogoutType.ADMIN_REVOKED,
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            ),
        )
    except Exception:
        log.warning("Failed to emit admin logout event")
