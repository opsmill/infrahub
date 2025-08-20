from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import jwt
import ujson
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from opentelemetry import trace
from pydantic import BaseModel, HttpUrl

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
router = APIRouter(prefix="/oidc")


class OIDCDiscoveryConfig(BaseModel):
    issuer: HttpUrl
    authorization_endpoint: HttpUrl
    token_endpoint: HttpUrl
    userinfo_endpoint: HttpUrl
    jwks_uri: HttpUrl
    revocation_endpoint: HttpUrl | None = None
    registration_endpoint: HttpUrl | None = None
    introspection_endpoint: HttpUrl | None = None
    end_session_endpoint: HttpUrl | None = None
    frontchannel_logout_supported: bool | None = None
    frontchannel_logout_session_supported: bool | None = None
    grant_types_supported: list[str] | None = None
    response_types_supported: list[str]
    subject_types_supported: list[str]
    id_token_signing_alg_values_supported: list[str]
    scopes_supported: list[str] | None = None
    token_endpoint_auth_methods_supported: list[str] | None = None
    claims_supported: list[str] | None = None
    acr_values_supported: list[str] | None = None
    request_parameter_supported: bool | None = None
    request_uri_parameter_supported: bool | None = None
    require_request_uri_registration: bool | None = None
    code_challenge_methods_supported: list[str] | None = None
    tls_client_certificate_bound_access_tokens: bool | None = None
    mtls_endpoint_aliases: dict[str, HttpUrl] | None = None


def _get_redirect_url(request: Request, provider_name: str) -> str:
    """Return public redirect URL."""
    base_url = config.SETTINGS.main.public_url or str(request.base_url)
    return urljoin(base_url, f"auth/oidc/{provider_name}/callback")


@router.get("/{provider_name:str}/authorize")
async def authorize(request: Request, provider_name: str, final_url: str | None = None) -> Response:
    provider = config.SETTINGS.security.get_oidc_provider(provider=provider_name)
    service: InfrahubServices = request.app.state.service

    response = await service.http.get(url=provider.discovery_url)
    _validate_response(response=response)
    oidc_config = OIDCDiscoveryConfig(**response.json())

    with trace.get_tracer(__name__).start_as_current_span("sso_oauth2_client_configuration") as span:
        span.set_attribute("provider_name", provider_name)
        span.set_attribute("scopes", provider.scopes)
        span.set_attribute("discovery_url", provider.discovery_url)

        client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            scope=provider.scopes,
        )

    redirect_uri = _get_redirect_url(request=request, provider_name=provider_name)
    final_url = final_url or config.SETTINGS.main.public_url or str(request.base_url)

    authorization_uri, state = client.create_authorization_url(
        url=str(oidc_config.authorization_endpoint), redirect_uri=redirect_uri, scope=provider.scopes
    )

    await service.cache.set(
        key=f"security:oidc:provider:{provider_name}:state:{state}", value=final_url, expires=KVTTL.TWO_HOURS
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
    provider = config.SETTINGS.security.get_oidc_provider(provider=provider_name)

    service: InfrahubServices = request.app.state.service

    cache_key = f"security:oidc:provider:{provider_name}:state:{state}"
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

    discovery_response = await service.http.get(url=provider.discovery_url)
    _validate_response(response=discovery_response)

    oidc_config = OIDCDiscoveryConfig(**discovery_response.json())

    token_response = await service.http.post(str(oidc_config.token_endpoint), data=token_data)
    _validate_response(response=token_response)

    with trace.get_tracer(__name__).start_as_current_span("sso_token_request") as span:
        span.set_attribute("token_request_data", ujson.dumps(token_response.json()))
        payload: dict[str, Any] = token_response.json()

    headers = {"Authorization": f"{payload.get('token_type')} {payload.get('access_token')}"}

    if provider.userinfo_method == config.UserInfoMethod.GET:
        userinfo_response = await service.http.get(str(oidc_config.userinfo_endpoint), headers=headers)
    else:
        userinfo_response = await service.http.post(str(oidc_config.userinfo_endpoint), headers=headers)

    _validate_response(response=userinfo_response)
    user_info: dict[str, Any] = userinfo_response.json()
    sso_groups = user_info.get("groups") or await _get_id_token_groups(
        oidc_config=oidc_config, service=service, payload=payload, client_id=provider.client_id
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
        access_token=user_token.access_token, refresh_token=user_token.refresh_token, final_url=stored_final_url
    )


def _validate_response(response: httpx.Response) -> None:
    if 200 <= response.status_code <= 299:
        return

    log.error(
        "Invalid response from the OIDC provider",
        url=response.url,
        status_code=response.status_code,
        body=response.json(),
    )
    raise GatewayError(message="Invalid response from Authentication provider")


async def _get_id_token_groups(
    oidc_config: OIDCDiscoveryConfig, service: InfrahubServices, payload: dict[str, Any], client_id: str
) -> list[str]:
    id_token = payload.get("id_token")
    if not id_token:
        return []
    jwks = await service.http.get(url=str(oidc_config.jwks_uri))

    jwk_client = jwt.PyJWKClient(uri=str(oidc_config.jwks_uri), cache_jwk_set=True)
    if jwk_client.jwk_set_cache:
        jwk_client.jwk_set_cache.put(jwks.json())

    signing_key = jwk_client.get_signing_key_from_jwt(id_token)

    decoded_token: dict[str, Any] = jwt.decode(
        jwt=id_token,
        key=signing_key.key,
        algorithms=oidc_config.id_token_signing_alg_values_supported,
        audience=client_id,
        issuer=str(oidc_config.issuer),
        options={"verify_signature": False, "verify_aud": False, "verify_iss": False},
    )

    return decoded_token.get("groups", [])
