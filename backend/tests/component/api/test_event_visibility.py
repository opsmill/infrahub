"""Admin-only visibility for account events in the InfrahubEvent GraphQL query.

Non-admin users must not be able to see login/logout activity. The resolver in
``backend/infrahub/graphql/queries/event.py`` enforces this via the
``MANAGE_ACCOUNTS`` global permission:

* An explicit filter on an ``infrahub.account.*`` event type raises
  ``PermissionDeniedError``.
* An unfiltered query silently excludes the account prefix for non-admins.
* An admin passes both checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from infrahub.core.constants import InfrahubKind

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


ACCOUNT_EVENT_QUERY = """
query($event_type: [String!]) {
  InfrahubEvent(event_type: $event_type, limit: 5, order: DESC) {
    count
    edges { node { id event } }
  }
}
"""

UNFILTERED_EVENT_QUERY = """
query {
  InfrahubEvent(limit: 5, order: DESC) {
    count
    edges { node { id event } }
  }
}
"""


async def test_non_admin_explicit_account_filter_denied(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    from infrahub.core.node import Node as CoreNode

    token = await CoreNode.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token="regression-nonadmin-deny", account=first_account.id)
    await token.save(db=db)

    with patch(
        "infrahub.task_manager.event.PrefectEvent.query",
        new=AsyncMock(return_value={"count": 0, "edges": []}),
    ):
        with client:
            resp = client.post(
                "/graphql",
                json={
                    "query": ACCOUNT_EVENT_QUERY,
                    "variables": {"event_type": ["infrahub.account.logged_in"]},
                },
                headers={"X-INFRAHUB-KEY": "regression-nonadmin-deny"},
            )

    body = resp.json()
    assert resp.status_code == 200
    assert body.get("errors"), f"expected permission error, got {body}"
    assert any(
        kw in (e.get("message") or "").lower() for e in body["errors"] for kw in ("permission", "denied", "not allowed")
    ), body["errors"]


async def test_non_admin_unfiltered_excludes_account_events(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    first_account: Node,
) -> None:
    """Unfiltered query by non-admin: no error, account prefix passed as exclude_prefix."""
    from infrahub.core.node import Node as CoreNode

    token = await CoreNode.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token="regression-nonadmin-excl", account=first_account.id)
    await token.save(db=db)

    observed_filters: list[Any] = []

    async def fake_query(**kwargs: Any) -> dict[str, Any]:
        observed_filters.append(kwargs["event_filter"])
        return {"count": 0, "edges": []}

    with patch("infrahub.task_manager.event.PrefectEvent.query", new=fake_query):
        with client:
            resp = client.post(
                "/graphql",
                json={"query": UNFILTERED_EVENT_QUERY},
                headers={"X-INFRAHUB-KEY": "regression-nonadmin-excl"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert not body.get("errors"), body
    assert observed_filters, "PrefectEvent.query was not invoked"
    event_name_filter = getattr(observed_filters[-1], "event", None)
    assert event_name_filter is not None
    assert list(getattr(event_name_filter, "exclude_prefix", []) or []) == ["infrahub.account."]


async def test_admin_can_filter_account_events(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    create_test_admin: Node,
) -> None:
    observed_filters: list[Any] = []

    async def fake_query(**kwargs: Any) -> dict[str, Any]:
        observed_filters.append(kwargs["event_filter"])
        return {"count": 0, "edges": []}

    with patch("infrahub.task_manager.event.PrefectEvent.query", new=fake_query):
        with client:
            resp = client.post(
                "/graphql",
                json={
                    "query": ACCOUNT_EVENT_QUERY,
                    "variables": {"event_type": ["infrahub.account.logged_in"]},
                },
                headers={"X-INFRAHUB-KEY": "admin-security"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert not body.get("errors"), body
    assert observed_filters, "PrefectEvent.query was not invoked for admin"
