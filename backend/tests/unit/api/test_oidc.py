from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from typing import Any

import httpx
import pytest
from jwcrypto import jwk, jwt
from pydantic import HttpUrl
from structlog.testing import capture_logs

from infrahub.api.oidc import OIDCDiscoveryConfig, _get_id_token_groups
from infrahub.config import SecurityOIDCSettings
from infrahub.exceptions import AuthorizationError, HTTPServerError
from infrahub.services import InfrahubServices
from tests.adapters.http import MemoryHTTP

CLIENT_ID = "testing-oicd-1234"


def _make_provider(verify_signature: bool = True) -> SecurityOIDCSettings:
    return SecurityOIDCSettings(
        client_id=CLIENT_ID,
        discovery_url="https://oidc.example.com/.well-known/openid-configuration",
        id_token_verify_signature=verify_signature,
    )


@pytest.fixture
def memory_http() -> MemoryHTTP:
    return MemoryHTTP()


@pytest.fixture
async def service(memory_http: MemoryHTTP) -> InfrahubServices:
    return await InfrahubServices.new(http=memory_http)


@pytest.fixture
def helper() -> OIDCTestHelper:
    return OIDCTestHelper()


def _serve_jwks_raw(memory_http: MemoryHTTP, content: bytes) -> None:
    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=content),
    )


def _serve_jwks(memory_http: MemoryHTTP, jwks: dict[str, Any]) -> None:
    _serve_jwks_raw(memory_http, json.dumps(jwks).encode())


@pytest.fixture
def publish_jwks(memory_http: MemoryHTTP, helper: OIDCTestHelper) -> None:
    """Serve the helper's public key at the discovery JWKS endpoint so signatures validate."""
    _serve_jwks(memory_http, helper.jwks_payload)


def _token_response(helper: OIDCTestHelper, client_id: str = CLIENT_ID) -> dict[str, Any]:
    return helper.generate_token_response(
        username="testuser",
        groups=["operators"],
        client_id=client_id,
        issuer=str(OIDC_CONFIG.issuer),
    )


def _forged_jwks(helper: OIDCTestHelper) -> dict[str, Any]:
    """A JWKS whose key does not match the token signature, under the same kid so resolution still succeeds."""
    attacker = OIDCTestHelper()
    return {"keys": [{**json.loads(attacker.key.export_public()), "kid": helper.kid}]}


async def test_get_id_token_groups_for_oidc(
    service: InfrahubServices, helper: OIDCTestHelper, publish_jwks: None
) -> None:
    groups = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=_token_response(helper),
        provider_settings=_make_provider(),
    )

    assert groups == ["operators"]


async def test_get_id_token_groups_rejects_invalid_issuer_by_default(
    service: InfrahubServices, helper: OIDCTestHelper, publish_jwks: None
) -> None:
    """With signature verification on (the default) a wrong issuer must abort, not be silently accepted."""
    discovery = deepcopy(OIDC_CONFIG)
    discovery.issuer = HttpUrl("https://something-incorrect.example.com")

    with pytest.raises(AuthorizationError, match=r"^OIDC id_token verification failed: Invalid issuer$"):
        await _get_id_token_groups(
            oidc_config=discovery,
            service=service,
            payload=_token_response(helper),
            provider_settings=_make_provider(),
        )


async def test_get_id_token_groups_rejects_invalid_audience_by_default(
    service: InfrahubServices, helper: OIDCTestHelper, publish_jwks: None
) -> None:
    """With signature verification on (the default) a token issued for another client must be rejected."""
    with pytest.raises(AuthorizationError, match=r"^OIDC id_token verification failed: Audience doesn't match$"):
        await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=_token_response(helper, client_id="some-other-client"),
            provider_settings=_make_provider(),
        )


async def test_get_id_token_groups_accepts_invalid_issuer_when_verification_disabled(
    service: InfrahubServices, helper: OIDCTestHelper, publish_jwks: None
) -> None:
    """Explicit opt-out preserves the legacy unverified behavior for a misconfigured provider."""
    discovery = deepcopy(OIDC_CONFIG)
    discovery.issuer = HttpUrl("https://something-incorrect.example.com")

    groups = await _get_id_token_groups(
        oidc_config=discovery,
        service=service,
        payload=_token_response(helper),
        provider_settings=_make_provider(verify_signature=False),
    )

    assert groups == ["operators"]


async def test_get_id_token_groups_rejects_forged_signature(
    memory_http: MemoryHTTP, service: InfrahubServices, helper: OIDCTestHelper
) -> None:
    """A token whose signature does not match the published key is rejected as an authorization error."""
    _serve_jwks(memory_http, _forged_jwks(helper))

    with pytest.raises(AuthorizationError, match=r"^OIDC id_token verification failed: Signature verification failed$"):
        await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=_token_response(helper),
            provider_settings=_make_provider(),
        )


async def test_get_id_token_groups_accepts_invalid_audience_when_verification_disabled(
    service: InfrahubServices, helper: OIDCTestHelper, publish_jwks: None
) -> None:
    """Explicit opt-out skips the audience claim check for a misconfigured provider."""
    groups = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=_token_response(helper, client_id="some-other-client"),
        provider_settings=_make_provider(verify_signature=False),
    )

    assert groups == ["operators"]


async def test_get_id_token_groups_accepts_forged_signature_when_verification_disabled(
    memory_http: MemoryHTTP, service: InfrahubServices, helper: OIDCTestHelper
) -> None:
    """Explicit opt-out skips the signature check, so a key that does not match is still accepted."""
    _serve_jwks(memory_http, _forged_jwks(helper))

    groups = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=_token_response(helper),
        provider_settings=_make_provider(verify_signature=False),
    )

    assert groups == ["operators"]


@pytest.mark.parametrize("verify_signature", [True, False])
async def test_get_id_token_groups_empty_jwks_raises_authorization_error(
    memory_http: MemoryHTTP, service: InfrahubServices, helper: OIDCTestHelper, verify_signature: bool
) -> None:
    """An empty/broken JWKS endpoint is wrapped as a clean error regardless of the verification flag.

    Signing-key resolution happens before the claim/signature checks, so the encapsulation must
    hold whether or not verification is enabled.
    """
    _serve_jwks(memory_http, {"keys": []})

    with pytest.raises(
        AuthorizationError, match=r"^OIDC id_token verification failed: The JWK Set did not contain any keys$"
    ):
        await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=_token_response(helper),
            provider_settings=_make_provider(verify_signature=verify_signature),
        )


@pytest.mark.parametrize("verify_signature", [True, False])
async def test_get_id_token_groups_non_json_jwks_raises_http_server_error(
    memory_http: MemoryHTTP, service: InfrahubServices, helper: OIDCTestHelper, verify_signature: bool
) -> None:
    """A JWKS endpoint returning a non-JSON body is an upstream failure, surfaced as a gateway error.

    The parse happens before any claim/signature check, so the behavior is independent of the flag.
    """
    _serve_jwks_raw(memory_http, b"<html>Bad Gateway</html>")

    with pytest.raises(HTTPServerError) as exc_info:
        await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=_token_response(helper),
            provider_settings=_make_provider(verify_signature=verify_signature),
        )

    assert exc_info.value.message == f"OIDC provider returned a non-JSON JWKS response from {OIDC_CONFIG.jwks_uri}"


@pytest.mark.parametrize("verify_signature", [True, False])
async def test_get_id_token_groups_malformed_id_token_raises_authorization_error(
    service: InfrahubServices, helper: OIDCTestHelper, publish_jwks: None, verify_signature: bool
) -> None:
    """A malformed id_token is wrapped as a clean error regardless of the verification flag."""
    token_response = _token_response(helper)
    token_response["id_token"] = "not-a-jwt"

    with pytest.raises(AuthorizationError, match=r"^OIDC id_token verification failed: Not enough segments$"):
        await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=token_response,
            provider_settings=_make_provider(verify_signature=verify_signature),
        )


async def test_get_id_token_groups_for_oidc_no_id_token(service: InfrahubServices, helper: OIDCTestHelper) -> None:
    token_response = _token_response(helper)
    token_response.pop("id_token")

    groups = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=token_response,
        provider_settings=_make_provider(),
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

    def generate_token_response(
        self,
        username: str,
        groups: list[str],
        client_id: str,
        issuer: str,
        *,
        claim_key: str = "groups",
    ) -> dict[str, Any]:
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
                claim_key: groups,
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


async def test_get_id_token_groups_with_custom_claim_key() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    client_id = "testing-oidc-roles"

    helper = OIDCTestHelper()
    token_response = helper.generate_token_response(
        username="testuser",
        groups=["network-engineering"],
        client_id=client_id,
        issuer=str(OIDC_CONFIG.issuer),
        claim_key="roles",
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
        claim_key="roles",
        provider_name="provider1",
    )

    assert groups == ["network-engineering"]


async def test_get_id_token_groups_with_custom_claim_key_miss_emits_warning() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    client_id = "testing-oidc-miss"

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

    with capture_logs() as records:
        groups = await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=token_response,
            client_id=client_id,
            claim_key="roles",
            provider_name="provider1",
        )

    assert groups == []
    warnings = [r for r in records if r.get("event") == "sso groups claim miss"]
    assert len(warnings) == 1
    assert warnings[0]["source"] == "oidc_id_token"
    assert warnings[0]["configured_claim"] == "roles"
    assert warnings[0]["miss_reason"] == "absent"
    assert warnings[0]["provider"] == "provider1"


async def test_default_claim_key_preserves_existing_behavior() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    client_id = "testing-oidc-default"

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

    with capture_logs() as records:
        groups = await _get_id_token_groups(
            oidc_config=OIDC_CONFIG,
            service=service,
            payload=token_response,
            client_id=client_id,
        )

    assert groups == ["operators"]
    assert not any(r.get("event") == "sso groups claim miss" for r in records)


async def test_two_providers_use_independent_claim_keys() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    client_id_1 = "testing-oidc-p1"
    client_id_2 = "testing-oidc-p2"

    helper = OIDCTestHelper()
    token_response_provider1 = helper.generate_token_response(
        username="alice",
        groups=["ops"],
        client_id=client_id_1,
        issuer=str(OIDC_CONFIG.issuer),
        claim_key="roles",
    )
    token_response_provider2 = helper.generate_token_response(
        username="bob",
        groups=["dev"],
        client_id=client_id_2,
        issuer=str(OIDC_CONFIG.issuer),
    )

    memory_http.add_get_response(
        url=str(OIDC_CONFIG.jwks_uri),
        response=httpx.Response(status_code=200, content=json.dumps(helper.jwks_payload)),
    )

    groups_p2 = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=token_response_provider2,
        client_id=client_id_2,
    )
    groups_p1 = await _get_id_token_groups(
        oidc_config=OIDC_CONFIG,
        service=service,
        payload=token_response_provider1,
        client_id=client_id_1,
        claim_key="roles",
        provider_name="provider1",
    )

    assert groups_p1 == ["ops"]
    assert groups_p2 == ["dev"]
