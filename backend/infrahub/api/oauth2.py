from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urljoin

import ujson
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from opentelemetry import trace

from infrahub import config, models
from infrahub.api.dependencies import get_db
from infrahub.auth import signin_sso_account
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
    """Return public redirect URL."""
    base_url = config.SETTINGS.main.public_url or str(request.base_url)
    return urljoin(base_url, f"auth/oauth2/{provider_name}/callback")


@router.get("/{provider_name:str}/authorize")
async def authorize(request: Request, provider_name: str, final_url: str | None = None) -> Response:
    provider = config.SETTINGS.security.get_oauth2_provider(provider=provider_name)

    with trace.get_tracer(__name__).start_as_current_span("sso_oauth2_client_configuration") as span:
        span.set_attribute("provider_name", provider_name)
        span.set_attribute("scopes", provider.scopes)

        client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            scope=provider.scopes,
        )

    redirect_uri = _get_redirect_url(request=request, provider_name=provider_name)
    final_url = final_url or config.SETTINGS.main.public_url or str(request.base_url)

    authorization_uri, state = client.create_authorization_url(
        url=provider.authorization_url, redirect_uri=redirect_uri, scope=provider.scopes, final_url=final_url
    )

    service: InfrahubServices = request.app.state.service

    await service.cache.set(
        key=f"security:oauth2:provider:{provider_name}:state:{state}", value=final_url, expires=KVTTL.TWO_HOURS
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
) -> models.UserTokenWithUrl:
    provider = config.SETTINGS.security.get_oauth2_provider(provider=provider_name)

    service: InfrahubServices = request.app.state.service

    cache_key = f"security:oauth2:provider:{provider_name}:state:{state}"
    stored_final_url = await service.cache.get(key=cache_key)
    await service.cache.delete(key=cache_key)

    if not stored_final_url:
        raise ProcessingError(message="Invalid 'state' parameter")

    token_data = {
        "code": code,
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "redirect_uri": _get_redirect_url(request=request, provider_name=provider_name),
        "grant_type": "authorization_code",
    }

    token_response = await service.http.post(provider.token_url, data=token_data)
    _validate_response(response=token_response)

    with trace.get_tracer(__name__).start_as_current_span("sso_token_request") as span:
        span.set_attribute("token_request_data", ujson.dumps(token_response.json()))
        payload = token_response.json()

    headers = {"Authorization": f"{payload.get('token_type')} {payload.get('access_token')}"}
    if provider.userinfo_method == config.UserInfoMethod.GET:
        userinfo_response = await service.http.get(provider.userinfo_url, headers=headers)
    else:
        userinfo_response = await service.http.post(provider.userinfo_url, headers=headers)

    _validate_response(response=userinfo_response)
    user_info = userinfo_response.json()
    sso_groups = user_info.get("groups", [])
    if not sso_groups and config.SETTINGS.security.sso_user_default_group:
        sso_groups = [config.SETTINGS.security.sso_user_default_group]

    with trace.get_tracer(__name__).start_as_current_span("signin_sso_account") as span:
        span.set_attribute("account_name", ujson.dumps(userinfo_response.json()))
        span.set_attribute("sso_groups", sso_groups)
        user_token = await signin_sso_account(db=db, account_name=user_info["name"], sso_groups=sso_groups)

    response.set_cookie(
        "access_token", user_token.access_token, httponly=True, max_age=config.SETTINGS.security.access_token_lifetime
    )
    response.set_cookie(
        "refresh_token",
        user_token.refresh_token,
        httponly=True,
        max_age=config.SETTINGS.security.refresh_token_lifetime,
    )

    return models.UserTokenWithUrl(
        access_token=user_token.access_token, refresh_token=user_token.refresh_token, final_url=stored_final_url
    )


def _validate_response(response: httpx.Response) -> None:
    if 200 <= response.status_code <= 299:
        return

    log.error(
        "Invalid response from the OAuth provider",
        url=response.url,
        status_code=response.status_code,
        body=response.json(),
    )
    raise GatewayError(message="Invalid response from Authentication provider")
