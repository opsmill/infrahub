import json

import httpx
from structlog.testing import capture_logs

from infrahub.auth.auth import extract_sso_groups
from infrahub.config import SecurityOAuth2Provider1
from infrahub.services import InfrahubServices
from tests.adapters.http import MemoryHTTP


def _build_provider(groups_claim: str = "groups") -> SecurityOAuth2Provider1:
    return SecurityOAuth2Provider1(
        client_id="infrahub-user-client",
        client_secret="secret",
        authorization_url="https://idp.example.com/auth",
        token_url="https://idp.example.com/token",
        userinfo_url="https://idp.example.com/userinfo",
        groups_claim=groups_claim,
    )


async def test_oauth2_userinfo_extracts_groups_from_custom_claim_key() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    provider = _build_provider(groups_claim="roles")

    userinfo_body = {
        "sub": "u1",
        "name": "Otto",
        "email": "o@x.com",
        "roles": ["network-engineering"],
    }
    memory_http.add_get_response(
        url=provider.userinfo_url,
        response=httpx.Response(status_code=200, content=json.dumps(userinfo_body)),
    )

    userinfo_response = await service.http.get(provider.userinfo_url)
    user_info = userinfo_response.json()

    sso_groups = extract_sso_groups(
        payload=user_info,
        claim_key=provider.groups_claim,
        provider_name="provider1",
        source="oauth2_userinfo",
    )

    assert sso_groups == ["network-engineering"]


async def test_oauth2_userinfo_custom_claim_key_does_not_read_groups_key() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    provider = _build_provider(groups_claim="roles")

    userinfo_body = {
        "sub": "u1",
        "name": "Otto",
        "email": "o@x.com",
        "groups": ["legacy-group"],
    }
    memory_http.add_get_response(
        url=provider.userinfo_url,
        response=httpx.Response(status_code=200, content=json.dumps(userinfo_body)),
    )

    userinfo_response = await service.http.get(provider.userinfo_url)
    user_info = userinfo_response.json()

    with capture_logs() as records:
        sso_groups = extract_sso_groups(
            payload=user_info,
            claim_key=provider.groups_claim,
            provider_name="provider1",
            source="oauth2_userinfo",
        )

    assert sso_groups == []
    warnings = [r for r in records if r.get("event") == "sso groups claim miss"]
    assert len(warnings) == 1
    assert warnings[0]["miss_reason"] == "absent"
    assert warnings[0]["source"] == "oauth2_userinfo"


async def test_default_claim_key_preserves_existing_behavior() -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)
    provider = _build_provider()

    assert provider.groups_claim == "groups"

    userinfo_body = {
        "sub": "u",
        "name": "Otto",
        "email": "o@x.com",
        "groups": ["admin-otter"],
    }
    memory_http.add_get_response(
        url=provider.userinfo_url,
        response=httpx.Response(status_code=200, content=json.dumps(userinfo_body)),
    )

    userinfo_response = await service.http.get(provider.userinfo_url)
    user_info = userinfo_response.json()

    with capture_logs() as records:
        sso_groups = extract_sso_groups(
            payload=user_info,
            claim_key=provider.groups_claim,
            provider_name="provider1",
            source="oauth2_userinfo",
        )

    assert sso_groups == ["admin-otter"]
    assert not any(r.get("event") == "sso groups claim miss" for r in records)


async def test_oauth2_and_oidc_with_different_claim_keys_coexist() -> None:
    oauth2_provider = _build_provider(groups_claim="memberships")
    oauth2_payload = {
        "sub": "u1",
        "name": "Otto",
        "email": "o@x.com",
        "memberships": ["membership-a"],
    }
    oauth2_groups = extract_sso_groups(
        payload=oauth2_payload,
        claim_key=oauth2_provider.groups_claim,
        provider_name="provider1",
        source="oauth2_userinfo",
    )

    oidc_payload = {
        "sub": "u2",
        "name": "Otto",
        "email": "o@x.com",
        "roles": ["role-x"],
    }
    oidc_groups = extract_sso_groups(
        payload=oidc_payload,
        claim_key="roles",
        provider_name="provider2",
        source="oidc_id_token",
    )

    assert oauth2_groups == ["membership-a"]
    assert oidc_groups == ["role-x"]
