from dataclasses import dataclass
from typing import Any

import pytest
from structlog.testing import capture_logs

from infrahub.auth.auth import extract_sso_groups


@dataclass
class HitCase:
    name: str
    claim_key: str
    payload: dict[str, Any]
    expected: list[str]


HIT_CASES: list[HitCase] = [
    HitCase(
        name="default_key_with_groups",
        claim_key="groups",
        payload={"sub": "u1", "name": "Otto", "email": "o@x.com", "groups": ["admins"]},
        expected=["admins"],
    ),
    HitCase(
        name="default_key_empty_list",
        claim_key="groups",
        payload={"sub": "u1", "groups": []},
        expected=[],
    ),
    HitCase(
        name="custom_key_roles",
        claim_key="roles",
        payload={"sub": "u1", "name": "Otto", "email": "o@x.com", "roles": ["network-engineering"]},
        expected=["network-engineering"],
    ),
    HitCase(
        name="custom_key_memberships",
        claim_key="memberships",
        payload={"sub": "u1", "memberships": ["g1", "g2", "g3"]},
        expected=["g1", "g2", "g3"],
    ),
    HitCase(
        name="namespaced_uri_key",
        claim_key="https://example.com/claims/groups",
        payload={"sub": "u1", "https://example.com/claims/groups": ["ops"]},
        expected=["ops"],
    ),
]


@pytest.mark.parametrize("case", HIT_CASES, ids=lambda c: c.name)
def test_extract_sso_groups_hit_returns_list_verbatim(case: HitCase) -> None:
    with capture_logs() as records:
        result = extract_sso_groups(
            payload=case.payload,
            claim_key=case.claim_key,
            provider_name="provider1",
            source="oidc_userinfo",
        )
    assert result == case.expected
    assert all(record.get("event") != "sso groups claim miss" for record in records)


@dataclass
class MissCase:
    name: str
    claim_key: str
    payload: dict[str, Any]
    expected_reason: str


MISS_CASES: list[MissCase] = [
    MissCase(
        name="absent_key",
        claim_key="roles",
        payload={"sub": "u1", "groups": ["admins"]},
        expected_reason="absent",
    ),
    MissCase(
        name="value_is_string",
        claim_key="groups",
        payload={"sub": "u1", "groups": "admins"},
        expected_reason="not_list",
    ),
    MissCase(
        name="value_is_int",
        claim_key="groups",
        payload={"sub": "u1", "groups": 42},
        expected_reason="not_list",
    ),
    MissCase(
        name="value_is_dict",
        claim_key="groups",
        payload={"sub": "u1", "groups": {"a": "b"}},
        expected_reason="not_list",
    ),
    MissCase(
        name="value_is_none",
        claim_key="groups",
        payload={"sub": "u1", "groups": None},
        expected_reason="not_list",
    ),
    MissCase(
        name="list_with_int",
        claim_key="groups",
        payload={"sub": "u1", "groups": ["admin", 7]},
        expected_reason="list_has_non_string",
    ),
    MissCase(
        name="list_with_dict",
        claim_key="groups",
        payload={"sub": "u1", "groups": [{"name": "admin"}]},
        expected_reason="list_has_non_string",
    ),
]


@pytest.mark.parametrize("case", MISS_CASES, ids=lambda c: c.name)
def test_extract_sso_groups_miss_returns_empty_and_warns(case: MissCase) -> None:
    with capture_logs() as records:
        result = extract_sso_groups(
            payload=case.payload,
            claim_key=case.claim_key,
            provider_name="provider1",
            source="oidc_userinfo",
        )

    assert result == []

    warnings = [r for r in records if r.get("event") == "sso groups claim miss"]
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["log_level"] == "warning"
    assert warning["provider"] == "provider1"
    assert warning["source"] == "oidc_userinfo"
    assert warning["configured_claim"] == case.claim_key
    assert warning["available_keys"] == sorted(case.payload.keys())
    assert warning["miss_reason"] == case.expected_reason


def test_warning_never_includes_payload_values() -> None:
    payload = {
        "sub": "user-12345",
        "email": "otter@example.com",
        "name": "Otto the Otter",
        "aud": "client-abc",
        "iss": "https://idp.example.com/realms/infrahub",
        "fake_token": "eyJhbGciOiJSUzI1NiJ9.payload.signature",
    }
    sensitive_values = list(payload.values())

    with capture_logs() as records:
        extract_sso_groups(
            payload=payload,
            claim_key="roles",
            provider_name="provider1",
            source="oidc_userinfo",
        )

    warnings = [r for r in records if r.get("event") == "sso groups claim miss"]
    assert len(warnings) == 1
    serialized = repr(warnings[0])
    for value in sensitive_values:
        assert value not in serialized


def test_every_miss_emits_warning_no_throttling() -> None:
    payload_miss = {"sub": "u", "groups": ["admins"]}
    payload_hit = {"sub": "u", "roles": ["ops"]}

    with capture_logs() as records:
        for _ in range(3):
            extract_sso_groups(
                payload=payload_miss,
                claim_key="roles",
                provider_name="provider1",
                source="oidc_userinfo",
            )
        extract_sso_groups(
            payload=payload_hit,
            claim_key="roles",
            provider_name="provider1",
            source="oidc_userinfo",
        )
        extract_sso_groups(
            payload=payload_miss,
            claim_key="roles",
            provider_name="provider1",
            source="oidc_userinfo",
        )

    warnings = [r for r in records if r.get("event") == "sso groups claim miss"]
    assert len(warnings) == 4
