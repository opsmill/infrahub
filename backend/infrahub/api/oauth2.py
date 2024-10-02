from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from urllib.parse import urljoin
from uuid import uuid4

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from infrahub import config, models
from infrahub.api.dependencies import get_db
from infrahub.auth import create_db_refresh_token, generate_access_token, generate_refresh_token
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import GatewayError, ProcessingError
from infrahub.log import get_logger
from infrahub.message_bus.types import KVTTL

if TYPE_CHECKING:
    import httpx

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

log = get_logger()
router = APIRouter(prefix="/oauth2")


def _get_redirect_url(request: Request, provider_name: str) -> str:
    """This function is mostly to support local development when the frontend runs on different ports compared to the API."""
    base_url = config.SETTINGS.dev.frontend_url or str(request.base_url)
    return urljoin(base_url, f"auth/oauth2/{provider_name}/callback")


@router.get("/{provider_name:str}/authorize")
async def authorize(
    request: Request,
    provider_name: str,
) -> Response:
    provider = config.SETTINGS.security.get_provider(provider=provider_name)
    client = AsyncOAuth2Client(
        client_id=provider.client_id,
        client_secret=provider.client_secret,
        scope=provider.scope,
    )

    redirect_uri = _get_redirect_url(request=request, provider_name=provider_name)

    authorization_uri, state = client.create_authorization_url(
        url=provider.authorization_url, redirect_uri=redirect_uri, scope=provider.scope
    )

    service: InfrahubServices = request.app.state.service

    await service.cache.set(
        key=f"security:oauth2:provider:{provider_name}:state:{state}", value=state, expires=KVTTL.TWO_HOURS
    )

    if config.SETTINGS.dev.frontend_redirect_sso:
        return JSONResponse(content={"url": authorization_uri})

    return RedirectResponse(url=authorization_uri)


@router.get("/{provider_name:str}/token")
async def token(
    request: Request,
    response: Response,
    provider_name: str,
    state: str,
    code: str,
    db: InfrahubDatabase = Depends(get_db),
) -> models.UserToken:
    provider = config.SETTINGS.security.get_provider(provider=provider_name)

    service: InfrahubServices = request.app.state.service

    cache_key = f"security:oauth2:provider:{provider_name}:state:{state}"
    stored_state = await service.cache.get(key=cache_key)
    await service.cache.delete(key=cache_key)

    if state != stored_state:
        raise ProcessingError(message="Invalid 'state' parameter")

    token_data = {
        "code": code,
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "redirect_uri": _get_redirect_url(request=request, provider_name=provider_name),
        "grant_type": "authorization_code",
    }

    token_response = await service.http.post(provider.token_url, json=token_data)
    _validate_response(response=token_response)
    payload = token_response.json()

    headers = {"Authorization": f"{payload.get('token_type')} {payload.get('access_token')}"}
    userinfo_response = await service.http.post(provider.userinfo_url, headers=headers)
    _validate_response(response=userinfo_response)
    user_info = userinfo_response.json()

    account = await NodeManager.get_one_by_default_filter(db=db, id=user_info["name"], kind=InfrahubKind.ACCOUNT)

    if not account:
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name=user_info["name"], account_type="User", role="admin", password=str(uuid4()))
        await account.save(db=db)

    now = datetime.now(tz=timezone.utc)
    refresh_expires = now + timedelta(seconds=config.SETTINGS.security.refresh_token_lifetime)
    session_id = await create_db_refresh_token(db=db, account_id=account.id, expiration=refresh_expires)
    access_token = generate_access_token(account_id=account.id, role=account.role.value.value, session_id=session_id)
    refresh_token = generate_refresh_token(account_id=account.id, session_id=session_id, expiration=refresh_expires)
    user_token = models.UserToken(access_token=access_token, refresh_token=refresh_token)

    response.set_cookie(
        "access_token", user_token.access_token, httponly=True, max_age=config.SETTINGS.security.access_token_lifetime
    )
    response.set_cookie(
        "refresh_token",
        user_token.refresh_token,
        httponly=True,
        max_age=config.SETTINGS.security.refresh_token_lifetime,
    )

    return user_token


def _validate_response(response: httpx.Response) -> None:
    if 200 <= response.status_code <= 299:
        return

    log.error(
        "Invalid response for OAuth authentiation",
        url=response.url,
        status_code=response.status_code,
        body=response.json(),
    )
    raise GatewayError(message="Invalid response from Authentication provider")
