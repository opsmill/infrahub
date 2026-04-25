from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from infrahub.core.constants import InfrahubKind
from infrahub.events.account_action import AccountLoggedInEvent, AccountLoggedOutEvent, AuthMethod

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_password_login_emits_logged_in_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """Successful password login must emit AccountLoggedInEvent."""
    captured: list[AccountLoggedInEvent] = []

    async def capture(event: object) -> None:
        if isinstance(event, AccountLoggedInEvent):
            captured.append(event)

    with patch(
        "infrahub.services.adapters.event.InfrahubEventService.send",
        new=AsyncMock(side_effect=capture),
    ):
        with client:
            response = client.post(
                "/api/auth/login",
                json={"username": "First Account", "password": "FirstPassword123"},
            )

    assert response.status_code == 200

    assert len(captured) == 1
    event = captured[0]
    assert event.account_id == first_account.id
    assert event.account_name == "First Account"
    assert event.auth_method == AuthMethod.PASSWORD
    assert event.session_id
    assert event.timestamp is not None


async def test_logout_emits_logged_out_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """User-initiated logout must emit AccountLoggedOutEvent with logout_type=user_initiated."""
    captured: list[AccountLoggedOutEvent] = []

    async def capture(event: object) -> None:
        if isinstance(event, AccountLoggedOutEvent):
            captured.append(event)

    with client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "First Account", "password": "FirstPassword123"},
        )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    with patch(
        "infrahub.services.adapters.event.InfrahubEventService.send",
        new=AsyncMock(side_effect=capture),
    ):
        with client:
            logout_response = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"},
            )

    assert logout_response.status_code == 200

    assert len(captured) == 1
    event = captured[0]
    assert event.account_id == first_account.id
    assert event.session_id
    assert event.timestamp is not None


async def test_session_id_correlates_login_and_logout(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """The logout event's session_id must match the preceding login event's session_id."""
    login_events: list[AccountLoggedInEvent] = []
    logout_events: list[AccountLoggedOutEvent] = []

    async def capture(event: object) -> None:
        if isinstance(event, AccountLoggedInEvent):
            login_events.append(event)
        elif isinstance(event, AccountLoggedOutEvent):
            logout_events.append(event)

    with patch(
        "infrahub.services.adapters.event.InfrahubEventService.send",
        new=AsyncMock(side_effect=capture),
    ):
        with client:
            login = client.post(
                "/api/auth/login",
                json={"username": "First Account", "password": "FirstPassword123"},
            )
            assert login.status_code == 200
            access = login.json()["access_token"]
            logout = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {access}"},
            )
            assert logout.status_code == 200

    assert len(login_events) == 1
    assert len(logout_events) == 1
    assert login_events[0].session_id == logout_events[0].session_id
    assert logout_events[0].logout_type == "user_initiated"


async def test_api_key_auth_does_not_emit_login_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """API-key authentication must not emit AccountLoggedInEvent (spec FR-008)."""
    from infrahub.core.node import Node as CoreNode

    token = await CoreNode.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token="regression-api-key-auth", account=first_account.id)
    await token.save(db=db)

    captured: list[Any] = []

    async def capture(event: object) -> None:
        captured.append(event)

    with patch(
        "infrahub.services.adapters.event.InfrahubEventService.send",
        new=AsyncMock(side_effect=capture),
    ):
        with client:
            response = client.get(
                "/api/schema/summary",
                headers={"X-INFRAHUB-KEY": "regression-api-key-auth"},
            )

    assert response.status_code == 200
    assert [e for e in captured if isinstance(e, AccountLoggedInEvent)] == []


async def test_refresh_token_does_not_emit_login_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """Refreshing an access token must not emit an AccountLoggedInEvent."""
    with client:
        login = client.post(
            "/api/auth/login",
            json={"username": "First Account", "password": "FirstPassword123"},
        )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    captured: list[Any] = []

    async def capture(event: object) -> None:
        captured.append(event)

    with patch(
        "infrahub.services.adapters.event.InfrahubEventService.send",
        new=AsyncMock(side_effect=capture),
    ):
        with client:
            resp = client.post(
                "/api/auth/refresh",
                cookies={"refresh_token": refresh_token},
            )
    assert resp.status_code == 200
    assert [e for e in captured if isinstance(e, AccountLoggedInEvent)] == []


async def test_failed_login_does_not_emit_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """A failed login attempt must not emit any event."""
    captured: list[Any] = []

    async def capture(event: object) -> None:
        captured.append(event)

    with patch(
        "infrahub.services.adapters.event.InfrahubEventService.send",
        new=AsyncMock(side_effect=capture),
    ):
        with client:
            resp = client.post(
                "/api/auth/login",
                json={"username": "First Account", "password": "WRONG"},
            )

    assert resp.status_code in (401, 403)
    assert captured == []


async def test_login_succeeds_when_event_emission_raises(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """Login must succeed even when the event service raises — fire-and-forget contract."""

    async def raise_always(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("event bus unavailable")

    with patch(
        "infrahub.services.adapters.event.InfrahubEventService.send",
        new=AsyncMock(side_effect=raise_always),
    ):
        with client:
            resp = client.post(
                "/api/auth/login",
                json={"username": "First Account", "password": "FirstPassword123"},
            )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
