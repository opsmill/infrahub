import json
import time
import uuid
from copy import deepcopy
from typing import Any

import httpx
from jwcrypto import jwk, jwt
from pydantic import HttpUrl

from infrahub.api.oidc import OIDCDiscoveryConfig, _get_id_token_groups
from infrahub.services import InfrahubServices
from tests.adapters.http import MemoryHTTP


async def test_get_id_token_groups_for_oidc() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    client_id = "testing-oicd-1234"

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=client_id,
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
        client_id=client_id,
    )

    assert groups == ["operators"]


async def test_get_id_token_groups_for_oidc_invalid_issuer() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    client_id = "testing-oicd-1234"

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=client_id,
        issuer=str(OIDC_CONFIG.issuer),
    )

    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(helper.jwks_payload)),
    )
    config = deepcopy(OIDC_CONFIG)
    config.issuer = HttpUrl("https://something-incorrect.example.com")

    groups = await _get_id_token_groups(
        oidc_config=config,
        service=service,
        payload=token_response,
        client_id=client_id,
    )

    assert groups == ["operators"]


async def test_get_id_token_groups_for_oidc_no_id_token() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    client_id = "testing-oicd-1234"

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=client_id,
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
        client_id=client_id,
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
