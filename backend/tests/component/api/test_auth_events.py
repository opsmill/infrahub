from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

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
