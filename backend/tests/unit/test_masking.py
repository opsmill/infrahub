from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.masking import MASKING_RULES, mask_mapping, replace_url_queries_in_text


@dataclass(frozen=True)
class MaskedFieldTestCase:
    name: str
    key: str
    value: Any
    expected: Any


MASKED_FIELD_TEST_CASES: list[MaskedFieldTestCase] = [
    MaskedFieldTestCase(name="client_ip_old_convention", key="net.peer.ip", value="203.0.113.7", expected="[MASKED]"),
    MaskedFieldTestCase(
        name="client_ip_new_convention", key="client.address", value="203.0.113.7", expected="[MASKED]"
    ),
    MaskedFieldTestCase(name="client_ip_log_field", key="client_ip", value="203.0.113.7", expected="[MASKED]"),
    MaskedFieldTestCase(
        name="http_url_keeps_scheme_host_and_path",
        key="http.url",
        value="https://infrahub.example.com/api/oidc/provider1/token?code=abc&state=xyz",
        expected="https://infrahub.example.com/api/oidc/provider1/token?[MASKED]",
    ),
    MaskedFieldTestCase(
        name="http_target_keeps_path",
        key="http.target",
        value="/api/oidc/provider1/token?code=abc&state=xyz",
        expected="/api/oidc/provider1/token?[MASKED]",
    ),
    MaskedFieldTestCase(
        name="url_full_keeps_path",
        key="url.full",
        value="https://infrahub.example.com/api/oauth2/provider1/token?code=abc",
        expected="https://infrahub.example.com/api/oauth2/provider1/token?[MASKED]",
    ),
    MaskedFieldTestCase(
        name="url_keeps_path",
        key="url",
        value="https://idp.example.com/userinfo?code=abc",
        expected="https://idp.example.com/userinfo?[MASKED]",
    ),
    MaskedFieldTestCase(
        name="url_without_query_string_is_unchanged",
        key="http.url",
        value="https://infrahub.example.com/api/schema",
        expected="https://infrahub.example.com/api/schema",
    ),
    MaskedFieldTestCase(
        name="url_path_naming_a_token_is_unchanged",
        key="http.url",
        value="https://infrahub.example.com/api/oidc/provider1/token",
        expected="https://infrahub.example.com/api/oidc/provider1/token",
    ),
    MaskedFieldTestCase(name="url_that_is_not_a_string_is_masked", key="url", value=42, expected="[MASKED]"),
    MaskedFieldTestCase(name="url_query", key="url.query", value="code=abc&state=xyz", expected="[MASKED]"),
    MaskedFieldTestCase(name="account_name", key="account_name", value="grace", expected="[MASKED]"),
    MaskedFieldTestCase(name="token", key="sso.access_token", value="eyJhbGciOi", expected="[MASKED]"),
    MaskedFieldTestCase(name="token_in_upper_case", key="API_TOKEN", value="abc123", expected="[MASKED]"),
    MaskedFieldTestCase(name="password", key="ldap.password", value="hunter2", expected="[MASKED]"),
    MaskedFieldTestCase(name="secret", key="client_secret", value="s3cr3t", expected="[MASKED]"),
    MaskedFieldTestCase(name="email", key="user.Email", value="grace@example.com", expected="[MASKED]"),
    MaskedFieldTestCase(name="user_name", key="user_name", value="Grace", expected="[MASKED]"),
    MaskedFieldTestCase(name="username", key="enduser.username", value="grace", expected="[MASKED]"),
    MaskedFieldTestCase(name="value_that_is_not_a_string", key="token_count", value=3, expected="[MASKED]"),
    MaskedFieldTestCase(
        name="mapping_under_a_matching_key_is_masked_whole",
        key="token_response",
        value={"access_token": "eyJhbGciOi", "token_type": "Bearer"},
        expected="[MASKED]",
    ),
    MaskedFieldTestCase(
        name="cypher_text_is_kept",
        key="query",
        value="MATCH (n:Node {uuid: $node_id}) RETURN n",
        expected="MATCH (n:Node {uuid: $node_id}) RETURN n",
    ),
    MaskedFieldTestCase(
        name="query_name_is_kept", key="query_name", value="NodeGetListQuery", expected="NodeGetListQuery"
    ),
    MaskedFieldTestCase(
        name="nested_mapping_and_list_are_masked",
        key="body",
        value={"account_id": "acc-1", "details": [{"id_token": "jwt-123", "branch": "main"}, ("x", "y")]},
        expected={"account_id": "acc-1", "details": [{"id_token": "[MASKED]", "branch": "main"}, ("x", "y")]},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in MASKED_FIELD_TEST_CASES])
def test_mask_mapping(test_case: MaskedFieldTestCase) -> None:
    assert mask_mapping(data={test_case.key: test_case.value, "branch": "main"}) == {
        test_case.key: test_case.expected,
        "branch": "main",
    }


def test_mask_mapping_leaves_the_input_unchanged() -> None:
    data = {"password": "pw-123", "body": {"email": "grace@example.com", "items": [{"token": "tok"}]}}

    masked = mask_mapping(data=data)

    assert masked == {"password": "[MASKED]", "body": {"email": "[MASKED]", "items": [{"token": "[MASKED]"}]}}
    assert data == {"password": "pw-123", "body": {"email": "grace@example.com", "items": [{"token": "tok"}]}}


@dataclass(frozen=True)
class FreeTextTestCase:
    name: str
    text: str
    expected: str


FREE_TEXT_TEST_CASES: list[FreeTextTestCase] = [
    FreeTextTestCase(
        name="url_in_quotes",
        text="Client error '400 Bad Request' for url 'https://idp.example.com/token?code=abc&state=xyz'",
        expected="Client error '400 Bad Request' for url 'https://idp.example.com/token?[MASKED]'",
    ),
    FreeTextTestCase(
        name="url_followed_by_a_space",
        text="GET http://infrahub:8000/api/oidc/provider1/token?code=abc&state=xyz failed",
        expected="GET http://infrahub:8000/api/oidc/provider1/token?[MASKED] failed",
    ),
    FreeTextTestCase(
        name="every_url_is_masked",
        text="first https://a.example.com/x?token=1 then https://b.example.com/y?code=2",
        expected="first https://a.example.com/x?[MASKED] then https://b.example.com/y?[MASKED]",
    ),
    FreeTextTestCase(
        name="url_without_query_string_is_unchanged",
        text="Connection refused for url 'https://idp.example.com/token'",
        expected="Connection refused for url 'https://idp.example.com/token'",
    ),
    FreeTextTestCase(
        name="question_mark_outside_a_url_is_unchanged",
        text="Is the branch main? code=abc",
        expected="Is the branch main? code=abc",
    ),
    FreeTextTestCase(
        name="text_already_masked_is_unchanged",
        text="url 'https://idp.example.com/token?[MASKED]'",
        expected="url 'https://idp.example.com/token?[MASKED]'",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FREE_TEXT_TEST_CASES])
def test_replace_url_queries_in_text(test_case: FreeTextTestCase) -> None:
    assert replace_url_queries_in_text(text=test_case.text) == test_case.expected


# Keys that Infrahub sets on its own spans and log lines; masking one of them would hide data an operator needs.
INFRAHUB_TELEMETRY_KEYS: list[str] = [
    "query",
    "query_name",
    "query_id",
    "rows",
    "provider_name",
    "sso_group_count",
    "sso_groups",
    "groups",
    "account_id",
    "request_id",
    "trace_id",
    "correlation_id",
    "routing_key",
    "worker",
    "app",
    "branch",
    "base_branch_name",
    "diff_branch_name",
    "diff_id",
    "proposed_change_id",
    "name",
    "type",
    "operation",
    "status_code",
    "scopes",
    "pkce_enabled",
    "pkce_supported",
    "discovery_url",
    "lock_request_time",
    "lock_acquired_time",
    "event",
    "body",
    "logger",
    "level",
    "timestamp",
]


@pytest.mark.parametrize("key", INFRAHUB_TELEMETRY_KEYS)
def test_no_rule_masks_a_key_that_infrahub_sets(key: str) -> None:
    assert [rule for rule in MASKING_RULES if rule.applies_to(key)] == []
