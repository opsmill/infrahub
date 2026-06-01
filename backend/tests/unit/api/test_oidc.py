import json
import time
import uuid
from copy import deepcopy
from typing import Any

import httpx
import pytest
from jwcrypto import jwk, jwt
from pydantic import HttpUrl

from infrahub.api.oidc import OIDCDiscoveryConfig, _get_id_token_groups
from infrahub.config import SecurityOIDCSettings
from infrahub.exceptions import AuthorizationError
from infrahub.services import InfrahubServices
from tests.adapters.http import MemoryHTTP

CLIENT_ID = "testing-oicd-1234"


def _make_provider(verify_signature: bool = True) -> SecurityOIDCSettings:
    return SecurityOIDCSettings(
        client_id=CLIENT_ID,
        discovery_url="https://oidc.example.com/.well-known/openid-configuration",
        id_token_verify_signature=verify_signature,
    )


async def test_get_id_token_groups_for_oidc() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=CLIENT_ID,
        issuer=str(OIDC_CONFIG.issuer),
    )

    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(helper.jwks_payload)),
    )

    groups = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=token_response,
        provider=_make_provider(),
    )

    assert groups == ["operators"]


async def test_get_id_token_groups_rejects_invalid_issuer_by_default() -> None:
    """With signature verification on (the default) a wrong issuer must abort, not be silently accepted."""
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=CLIENT_ID,
        issuer=str(OIDC_CONFIG.issuer),
    )

    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(helper.jwks_payload)),
    )
    discovery = deepcopy(OIDC_CONFIG)
    discovery.issuer = HttpUrl("https://something-incorrect.example.com")

    with pytest.raises(AuthorizationError, match=r"^OIDC id_token verification failed: Invalid issuer$"):
        await _get_id_token_groups(
            oidc_config=discovery,
            service=service,
            payload=token_response,
            provider=_make_provider(),
        )


async def test_get_id_token_groups_rejects_invalid_audience_by_default() -> None:
    """With signature verification on (the default) a token issued for another client must be rejected."""
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id="some-other-client",
        issuer=str(OIDC_CONFIG.issuer),
    )

    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(helper.jwks_payload)),
    )

    with pytest.raises(AuthorizationError, match=r"^OIDC id_token verification failed: Audience doesn't match$"):
        await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=token_response,
            provider=_make_provider(),
        )


async def test_get_id_token_groups_accepts_invalid_issuer_when_verification_disabled() -> None:
    """Explicit opt-out preserves the legacy unverified behavior for a misconfigured provider."""
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=CLIENT_ID,
        issuer=str(OIDC_CONFIG.issuer),
    )

    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(helper.jwks_payload)),
    )
    discovery = deepcopy(OIDC_CONFIG)
    discovery.issuer = HttpUrl("https://something-incorrect.example.com")

    groups = await _get_id_token_groups(
        oidc_config=discovery,
        service=service,
        payload=token_response,
        provider=_make_provider(verify_signature=False),
    )

    assert groups == ["operators"]


async def test_get_id_token_groups_rejects_forged_signature() -> None:
    """A token whose signature does not match the published key is rejected as an authorization error."""
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=CLIENT_ID,
        issuer=str(OIDC_CONFIG.issuer),
    )

    # Publish a JWKS whose key does not match the one that signed the token, while
    # reusing the same kid so the signing key is still resolved and the signature check runs.
    attacker = OIDCTestHelper()
    forged_jwks = {"keys": [{**json.loads(attacker.key.export_public()), "kid": helper.kid}]}
    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(forged_jwks)),
    )

    with pytest.raises(AuthorizationError, match=r"^OIDC id_token verification failed: Signature verification failed$"):
        await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=token_response,
            provider=_make_provider(),
        )


async def test_get_id_token_groups_for_oidc_no_id_token() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=CLIENT_ID,
        issuer=str(OIDC_CONFIG.issuer),
    )
    token_response.pop("id_token")

    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(helper.jwks_payload)),
    )

    groups = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=token_response,
        provider=_make_provider(),
    )

    assert groups == []


class OIDCTestHelper:
    def __init__(self) -> None:
        self.key: jwk.JWK = jwk.JWK.generate(kty="RSA", size=2048)
        self.kid = str(uuid.uuid4())

        self.jwks_payload = {
            "keys": [
                {
                    **json.loads(self.key.export_public()),
                    "kid": self.kid,
                }
            ]
        }

    def generate_token_response(self, username: str, groups: list[str], client_id: str, issuer: str) -> dict[str, Any]:
        current_time = int(time.time())
        expiration_time = current_time + 600

        id_token = jwt.JWT(
            header={"alg": "RS256", "kid": self.kid},
            claims={
                "sub": str(uuid.uuid4()),
                "aud": client_id,
                "iss": issuer,
                "exp": expiration_time,
                "iat": current_time,
                "auth_time": current_time,
                "name": username,
                "groups": groups,
            },
        )
        id_token.make_signed_token(self.key)

        return {
            "access_token": id_token.serialize(),
            "expires_in": 600,
            "refresh_expires_in": 1800,
            "id_token": id_token.serialize(),
            "token_type": "Bearer",
            "scope": "openid profile email",
        }


OIDC_CONFIG = OIDCDiscoveryConfig(
    issuer=HttpUrl("https://oidc.example.com/realms/infrahub-oidc"),
    authorization_endpoint=HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/auth"),
    token_endpoint=HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/token"),
    userinfo_endpoint=HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/userinfo"),
    jwks_uri=HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/certs"),
    revocation_endpoint=HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/revoke"),
    registration_endpoint=HttpUrl("https://oidc.example.com/realms/infrahub-oidc/clients-registrations/openid-connect"),
    introspection_endpoint=HttpUrl(
        "https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/token/introspect"
    ),
    end_session_endpoint=HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/logout"),
    frontchannel_logout_supported=True,
    frontchannel_logout_session_supported=True,
    grant_types_supported=["authorization_code", "implicit"],
    response_types_supported=["code", "id_token", "token"],
    subject_types_supported=["public"],
    id_token_signing_alg_values_supported=["RS256"],
    scopes_supported=["openid", "profile", "email"],
    token_endpoint_auth_methods_supported=["client_secret_basic"],
    claims_supported=["sub", "name", "email"],
    acr_values_supported=["1"],
    request_parameter_supported=True,
    request_uri_parameter_supported=True,
    require_request_uri_registration=True,
    code_challenge_methods_supported=["S256"],
    tls_client_certificate_bound_access_tokens=True,
    mtls_endpoint_aliases={
        "token_endpoint": HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/token"),
        "revocation_endpoint": HttpUrl("https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/revoke"),
        "introspection_endpoint": HttpUrl(
            "https://oidc.example.com/realms/infrahub-oidc/protocol/openid-connect/token/introspect"
        ),
    },
)
