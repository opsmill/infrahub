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
from infrahub.auth import (
    SSOStateCache,
    get_groups_from_provider,
    signin_sso_account,
    validate_auth_response,
)
from infrahub.auth_pkce import compute_code_challenge, generate_code_verifier
from infrahub.exceptions import ProcessingError
from infrahub.log import get_logger
from infrahub.message_bus.types import KVTTL

if TYPE_CHECKING:
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
        span.set_attribute("pkce_enabled", provider.pkce_enabled)

        client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            scope=provider.scopes,
        )

    redirect_uri = _get_redirect_url(request=request, provider_name=provider_name)
    final_url = final_url or config.SETTINGS.main.public_url or str(request.base_url)

    # Generate PKCE parameters if enabled
    code_verifier = None
    pkce_params: dict[str, str] = {}
    if provider.pkce_enabled:
        code_verifier = generate_code_verifier()
        code_challenge = compute_code_challenge(code_verifier)
        pkce_params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

    authorization_uri, state = client.create_authorization_url(
        url=provider.authorization_url,
        redirect_uri=redirect_uri,
        scope=provider.scopes,
        final_url=final_url,
        **pkce_params,
    )

    service: InfrahubServices = request.app.state.service

    cache_data = SSOStateCache(final_url=final_url, code_verifier=code_verifier)
    await service.cache.set(
        key=f"security:oauth2:provider:{provider_name}:state:{state}",
        value=cache_data.model_dump_json(),
        expires=KVTTL.TWO_HOURS,
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
    cached_data = await service.cache.get(key=cache_key)
    await service.cache.delete(key=cache_key)

    if not cached_data:
        raise ProcessingError(message="Invalid 'state' parameter")

    sso_state = SSOStateCache.model_validate_json(cached_data)

    token_data: dict[str, str | None] = {
        "code": code,
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "redirect_uri": _get_redirect_url(request=request, provider_name=provider_name),
        "grant_type": "authorization_code",
    }

    # Add code_verifier if PKCE was used
    if sso_state.code_verifier:
        token_data["code_verifier"] = sso_state.code_verifier

    token_response = await service.http.post(provider.token_url, data=token_data)
    validate_auth_response(response=token_response, provider_type="OAuth 2.0")

    with trace.get_tracer(__name__).start_as_current_span("sso_token_request") as span:
        span.set_attribute("token_request_data", ujson.dumps(token_response.json()))
        payload = token_response.json()

    headers = {"Authorization": f"{payload.get('token_type')} {payload.get('access_token')}"}
    if provider.userinfo_method == config.UserInfoMethod.GET:
        userinfo_response = await service.http.get(provider.userinfo_url, headers=headers)
    else:
        userinfo_response = await service.http.post(provider.userinfo_url, headers=headers)

    validate_auth_response(response=userinfo_response, provider_type="OAuth 2.0")
    user_info = userinfo_response.json()
    sso_groups = user_info.get("groups", []) or await get_groups_from_provider(
        provider=provider, service=service, payload=payload, user_info=user_info
    )

    log.info(
        "SSO user authenticated",
        body={"user_name": user_info.get("name"), "groups": sso_groups},
    )

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
        access_token=user_token.access_token, refresh_token=user_token.refresh_token, final_url=sso_state.final_url
    )
