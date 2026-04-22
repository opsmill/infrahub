"""Builder-level coverage for login/logout activity event construction.

Complements the REST-level tests in ``tests/component/api/test_auth_events.py``
by exercising ``make_login_event`` / ``make_logout_event`` directly — they are
shared by the password, OAuth2 and OIDC endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import Request

from infrahub import models
from infrahub.api.event_builder import make_login_event, make_logout_event
from infrahub.auth import AccountSession, AuthResult, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.constants import AccountType, InfrahubKind
from infrahub.events.account_action import AuthMethod
from infrahub.events.models import EventMeta

if TYPE_CHECKING:
    from infrahub.core.branch import Branch


def _fake_request(headers: dict[str, str] | None = None, client_host: str | None = "10.1.2.3") -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def _auth_result(session_id: str = "11111111-1111-1111-1111-111111111111") -> AuthResult:
    return AuthResult(
        account_id="acct-xyz",
        account_name="someone",
        account_type=AccountType.USER,
        kind=InfrahubKind.ACCOUNT,
        session_id=UUID(session_id),
        groups=[{"group-id-1": "admins"}],
        roles=[{"role-id-1": "admin"}],
        token=models.UserToken(access_token="jwt", refresh_token="refresh"),
    )


def _event_meta(default_branch: Branch) -> EventMeta:
    session = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id="acct-xyz")
    return EventMeta(
        branch=default_branch,
        context=InfrahubContext.init(branch=default_branch, account=session),
        account_id="acct-xyz",
    )


def test_oauth2_login_event_sets_identity_source(default_branch: Branch) -> None:
    event = make_login_event(
        auth_result=_auth_result(),
        request=_fake_request({"user-agent": "curl/7.90"}),
        auth_method=AuthMethod.OAUTH2,
        event_meta=_event_meta(default_branch),
        identity_source="okta",
    )
    assert event.auth_method == AuthMethod.OAUTH2
    assert event.identity_source == "okta"
    assert event.client_ip == "10.1.2.3"
    assert event.user_agent == "curl/7.90"
    assert event.get_resource()["infrahub.account.identity_source"] == "okta"


def test_oidc_login_event_sets_identity_source(default_branch: Branch) -> None:
    event = make_login_event(
        auth_result=_auth_result(),
        request=_fake_request({"user-agent": "Mozilla"}),
        auth_method=AuthMethod.OIDC,
        event_meta=_event_meta(default_branch),
        identity_source="keycloak",
    )
    assert event.auth_method == AuthMethod.OIDC
    assert event.identity_source == "keycloak"


def test_login_client_ip_reads_socket_not_x_forwarded_for(default_branch: Branch) -> None:
    """client_ip comes from request.client.host; X-Forwarded-For is not consulted.

    This is the current behavior. If ProxyHeadersMiddleware (or equivalent) is
    ever wired up, this test must be updated along with any deployment docs.
    """
    event = make_login_event(
        auth_result=_auth_result(),
        request=_fake_request(
            headers={"x-forwarded-for": "203.0.113.7", "user-agent": "client"},
            client_host="172.18.0.5",
        ),
        auth_method=AuthMethod.PASSWORD,
        event_meta=_event_meta(default_branch),
    )
    assert event.client_ip == "172.18.0.5"


def test_logout_client_ip_reads_socket_not_x_forwarded_for(default_branch: Branch) -> None:
    event = make_logout_event(
        account_id="acct-xyz",
        account_name="someone",
        account_kind=InfrahubKind.ACCOUNT,
        session_id="sess-123",
        request=_fake_request(
            headers={"x-forwarded-for": "203.0.113.9", "user-agent": "q"},
            client_host="172.18.0.8",
        ),
        event_meta=_event_meta(default_branch),
    )
    assert event.client_ip == "172.18.0.8"
    assert event.logout_type == "user_initiated"
