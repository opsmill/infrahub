from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import AccountType
from infrahub.events.account_action import AccountLoggedInEvent, AccountLoggedOutEvent, AuthMethod
from infrahub.events.models import EventMeta


def _make_meta(account_id: str = "test-account-id") -> EventMeta:
    branch = MagicMock(spec=Branch)
    branch.name = "main"
    branch.uuid = uuid.uuid4()
    branch.get_uuid.return_value = branch.uuid
    return EventMeta(
        branch=branch,
        context=InfrahubContext.init(
            branch=branch,
            account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=account_id),
        ),
        account_id=account_id,
    )


def test_account_logged_in_get_resource() -> None:
    meta = _make_meta("acct-123")
    event = AccountLoggedInEvent(
        meta=meta,
        account_id="acct-123",
        account_name="testuser",
        account_type=AccountType.USER,
        auth_method=AuthMethod.PASSWORD,
        session_id="sess-456",
        groups=["admins"],
        roles=["admin-role"],
    )

    resource = event.get_resource()

    assert resource["prefect.resource.id"] == "infrahub.account.acct-123"
    assert resource["infrahub.account.name"] == "testuser"
    assert resource["infrahub.account.auth_method"] == "password"
    assert resource["infrahub.account.session_id"] == "sess-456"


def test_account_logged_in_get_payload() -> None:
    meta = _make_meta("acct-123")
    event = AccountLoggedInEvent(
        meta=meta,
        account_id="acct-123",
        account_name="testuser",
        account_type=AccountType.USER,
        auth_method=AuthMethod.PASSWORD,
        session_id="sess-456",
        groups=["admins"],
        roles=["admin-role"],
        sso_provider=None,
        client_ip="127.0.0.1",
        user_agent="TestBrowser/1.0",
    )

    payload = event.get_payload()

    assert payload["account_id"] == "acct-123"
    assert payload["account_name"] == "testuser"
    assert payload["account_type"] == "User"
    assert payload["auth_method"] == "password"
    assert payload["session_id"] == "sess-456"
    assert payload["groups"] == ["admins"]
    assert payload["roles"] == ["admin-role"]
    assert payload["sso_provider"] is None
    assert payload["client_ip"] == "127.0.0.1"
    assert payload["user_agent"] == "TestBrowser/1.0"
    assert "timestamp" in payload


def test_account_logged_in_timestamp_is_utc() -> None:
    meta = _make_meta()
    event = AccountLoggedInEvent(
        meta=meta,
        account_id="acct-123",
        account_name="testuser",
        account_type=AccountType.USER,
        auth_method=AuthMethod.PASSWORD,
        session_id="sess-456",
    )

    assert event.timestamp.tzinfo is not None
    assert event.timestamp.tzinfo == UTC or event.timestamp.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_account_logged_out_get_resource() -> None:
    meta = _make_meta("acct-789")
    event = AccountLoggedOutEvent(
        meta=meta,
        account_id="acct-789",
        account_name="testuser",
        session_id="sess-abc",
    )

    resource = event.get_resource()

    assert resource["prefect.resource.id"] == "infrahub.account.acct-789"
    assert resource["infrahub.account.name"] == "testuser"
    assert resource["infrahub.account.session_id"] == "sess-abc"
    assert resource["infrahub.account.logout_type"] == "user_initiated"


def test_account_logged_out_get_payload() -> None:
    meta = _make_meta("acct-789")
    event = AccountLoggedOutEvent(
        meta=meta,
        account_id="acct-789",
        account_name="testuser",
        session_id="sess-abc",
        client_ip="10.0.0.1",
        user_agent="TestClient/2.0",
    )

    payload = event.get_payload()

    assert payload["account_id"] == "acct-789"
    assert payload["account_name"] == "testuser"
    assert payload["session_id"] == "sess-abc"
    assert payload["logout_type"] == "user_initiated"
    assert payload["client_ip"] == "10.0.0.1"
    assert payload["user_agent"] == "TestClient/2.0"
    assert "timestamp" in payload


def test_account_logged_out_timestamp_is_utc() -> None:
    meta = _make_meta()
    event = AccountLoggedOutEvent(
        meta=meta,
        account_id="acct-789",
        account_name="testuser",
        session_id="sess-abc",
    )

    assert event.timestamp.tzinfo is not None
    assert event.timestamp.tzinfo == UTC or event.timestamp.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_account_logged_in_custom_timestamp() -> None:
    meta = _make_meta()
    custom_ts = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
    event = AccountLoggedInEvent(
        meta=meta,
        account_id="acct-123",
        account_name="testuser",
        account_type=AccountType.USER,
        auth_method=AuthMethod.PASSWORD,
        session_id="sess-456",
        timestamp=custom_ts,
    )

    assert event.timestamp == custom_ts
    payload = event.get_payload()
    assert payload["timestamp"] == custom_ts


def test_account_logged_out_custom_timestamp() -> None:
    meta = _make_meta()
    custom_ts = datetime(2026, 1, 15, 11, 0, 0, tzinfo=UTC)
    event = AccountLoggedOutEvent(
        meta=meta,
        account_id="acct-789",
        account_name="testuser",
        session_id="sess-abc",
        timestamp=custom_ts,
    )

    assert event.timestamp == custom_ts
    payload = event.get_payload()
    assert payload["timestamp"] == custom_ts
