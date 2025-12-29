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

    @property
    def supports_pkce(self) -> bool:
        return "S256" in (self.code_challenge_methods_supported or [])


def _get_redirect_url(request: Request, provider_name: str) -> str:
    """Return public redirect URL."""
    base_url = config.SETTINGS.main.public_url or str(request.base_url)
    return urljoin(base_url, f"auth/oidc/{provider_name}/callback")


@router.get("/{provider_name:str}/authorize")
async def authorize(request: Request, provider_name: str, final_url: str | None = None) -> Response:
    provider = config.SETTINGS.security.get_oidc_provider(provider=provider_name)
    service: InfrahubServices = request.app.state.service

    response = await service.http.get(url=provider.discovery_url)
    validate_auth_response(response=response, provider_type="OIDC")
    oidc_config = OIDCDiscoveryConfig(**response.json())

    pkce_supported = oidc_config.supports_pkce

    with trace.get_tracer(__name__).start_as_current_span("sso_oauth2_client_configuration") as span:
        span.set_attribute("provider_name", provider_name)
        span.set_attribute("scopes", provider.scopes)
        span.set_attribute("discovery_url", provider.discovery_url)
        span.set_attribute("pkce_enabled", provider.pkce_enabled)
        span.set_attribute("pkce_supported", pkce_supported)

        client = AsyncOAuth2Client(
            client_id=provider.client_id,
            client_secret=provider.client_secret,
            scope=provider.scopes,
        )

    redirect_uri = _get_redirect_url(request=request, provider_name=provider_name)
    final_url = final_url or config.SETTINGS.main.public_url or str(request.base_url)

    # Generate PKCE parameters if enabled and supported by provider
    code_verifier = None
    pkce_params: dict[str, str] = {}
    if provider.pkce_enabled and pkce_supported:
        code_verifier = generate_code_verifier()
        code_challenge = compute_code_challenge(code_verifier)
        pkce_params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

    authorization_uri, state = client.create_authorization_url(
        url=str(oidc_config.authorization_endpoint), redirect_uri=redirect_uri, scope=provider.scopes, **pkce_params
    )

    cache_data = SSOStateCache(final_url=final_url, code_verifier=code_verifier)
    await service.cache.set(
        key=f"security:oidc:provider:{provider_name}:state:{state}",
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
    provider = config.SETTINGS.security.get_oidc_provider(provider=provider_name)

    service: InfrahubServices = request.app.state.service

    cache_key = f"security:oidc:provider:{provider_name}:state:{state}"
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

    discovery_response = await service.http.get(url=provider.discovery_url)
    validate_auth_response(response=discovery_response, provider_type="OIDC")

    oidc_config = OIDCDiscoveryConfig(**discovery_response.json())

    token_response = await service.http.post(str(oidc_config.token_endpoint), data=token_data)
    validate_auth_response(response=token_response, provider_type="OIDC")

    with trace.get_tracer(__name__).start_as_current_span("sso_token_request") as span:
        span.set_attribute("token_request_data", ujson.dumps(token_response.json()))
        payload: dict[str, Any] = token_response.json()

    headers = {"Authorization": f"{payload.get('token_type')} {payload.get('access_token')}"}

    if provider.userinfo_method == config.UserInfoMethod.GET:
        userinfo_response = await service.http.get(str(oidc_config.userinfo_endpoint), headers=headers)
    else:
        userinfo_response = await service.http.post(str(oidc_config.userinfo_endpoint), headers=headers)

    validate_auth_response(response=userinfo_response, provider_type="OIDC")
    user_info: dict[str, Any] = userinfo_response.json()
    sso_groups = (
        user_info.get("groups")
        or await _get_id_token_groups(
            oidc_config=oidc_config, service=service, payload=payload, client_id=provider.client_id
        )
        or await get_groups_from_provider(provider=provider, service=service, payload=payload, user_info=user_info)
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
