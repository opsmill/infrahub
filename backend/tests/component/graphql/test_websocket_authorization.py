from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

import jwt
import pytest
from starlette.applications import Starlette

from infrahub import config
from infrahub.auth.auth import generate_access_token
from infrahub.core.constants import AccountStatus, InfrahubKind, PermissionDecision
from infrahub.core.node import Node
from infrahub.graphql.api.endpoints import router
from infrahub.graphql.app import subscription_tasks

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.types import Message, Scope

    from infrahub.database import InfrahubDatabase


TAG_QUERY = "query { BuiltinTag { edges { node { name { value } } } } }"


@dataclass(frozen=True)
class SubscriptionCase:
    name: str
    credential: Literal[
        "api",
        "bearer",
        "cookie",
        "invalid_api",
        "invalid_bearer",
        "expired",
        "api_precedence",
        "bearer_precedence",
        "none",
    ]
    expected: Literal["data", "denied", "closed"]
    identity: Literal["admin", "reader", "anonymous"] = "admin"
    allow_anonymous: bool = False
    allow_read: bool = False
    disable_anonymous_after_result: bool = False
    query: str = TAG_QUERY


@asynccontextmanager
async def _websocket_messages(
    db: InfrahubDatabase, headers: list[tuple[bytes, bytes]], interval: int = 10
) -> AsyncIterator[asyncio.Queue[Message]]:
    app = Starlette(routes=router.routes)
    app.state.db = db
    app.state.service = None
    incoming: asyncio.Queue[Message] = asyncio.Queue()
    outgoing: asyncio.Queue[Message] = asyncio.Queue()
    scope: Scope = {"type": "websocket", "path": "/graphql/main", "headers": headers, "query_string": b""}
    incoming.put_nowait({"type": "websocket.connect"})
    incoming.put_nowait(
        {
            "type": "websocket.receive",
            "text": json.dumps(
                {
                    "id": "1",
                    "type": "start",
                    "payload": {"query": f'subscription {{ query(name: "saved_query", interval: {interval}) }}'},
                }
            ),
        }
    )
    previous_tasks = subscription_tasks.copy()
    task = asyncio.create_task(app(scope=scope, receive=incoming.get, send=outgoing.put))
    try:
        async with asyncio.timeout(15):
            yield outgoing
    finally:
        started_tasks = subscription_tasks - previous_tasks
        for subscription_task in started_tasks:
            subscription_task.cancel()
        await asyncio.gather(*started_tasks, return_exceptions=True)
        incoming.put_nowait({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(task, timeout=10)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(case, id=case.name)
        for case in [
            SubscriptionCase(name="api_key", credential="api", expected="data"),
            SubscriptionCase(name="bearer", credential="bearer", expected="data"),
            SubscriptionCase(
                name="cookie_preserves_account_context",
                credential="cookie",
                expected="data",
                query="query { InfrahubAccountToken { count } }",
            ),
            SubscriptionCase(name="invalid_api_key", credential="invalid_api", expected="closed"),
            SubscriptionCase(name="invalid_bearer", credential="invalid_bearer", expected="closed"),
            SubscriptionCase(name="expired_bearer", credential="expired", expected="closed"),
            SubscriptionCase(name="api_key_precedes_cookie", credential="api_precedence", expected="data"),
            SubscriptionCase(name="bearer_precedes_cookie", credential="bearer_precedence", expected="closed"),
            SubscriptionCase(
                name="reader_without_permission", credential="bearer", identity="reader", expected="denied"
            ),
            SubscriptionCase(
                name="reader_with_permission", credential="bearer", identity="reader", allow_read=True, expected="data"
            ),
            SubscriptionCase(
                name="anonymous_without_permission",
                credential="none",
                identity="anonymous",
                allow_anonymous=True,
                expected="denied",
            ),
            SubscriptionCase(
                name="anonymous_with_permission",
                credential="none",
                identity="anonymous",
                allow_anonymous=True,
                allow_read=True,
                expected="data",
            ),
            SubscriptionCase(
                name="invalid_credentials_with_anonymous_access",
                credential="invalid_bearer",
                allow_anonymous=True,
                expected="closed",
            ),
            SubscriptionCase(
                name="anonymous_access_disabled_during_subscription",
                credential="none",
                identity="anonymous",
                allow_anonymous=True,
                allow_read=True,
                disable_anonymous_after_result=True,
                expected="data",
            ),
        ]
    ],
)
async def test_saved_query_subscription_permissions(
    db: InfrahubDatabase,
    create_test_admin: Node,
    default_permission_backend: None,
    monkeypatch: pytest.MonkeyPatch,
    case: SubscriptionCase,
) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", case.allow_anonymous)
    monkeypatch.setattr(config.SETTINGS.main, "anonymous_access_role", "subscription-reader")
    account = create_test_admin
    if case.identity == "reader":
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name="reader", account_type="User", password="ReaderPassword123")
        await account.save(db=db)
    if case.allow_read:
        permission = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await permission.new(
            db=db, namespace="Builtin", name="Tag", action="view", decision=PermissionDecision.ALLOW_ALL.value
        )
        await permission.save(db=db)
        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="subscription-reader", permissions=[permission])
        await role.save(db=db)
        if case.identity == "reader":
            group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
            await group.new(db=db, name="subscription-readers", roles=[role], members=[account])
            await group.save(db=db)

    tag = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag.new(db=db, name="visible-tag")
    await tag.save(db=db)
    saved_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await saved_query.new(db=db, name="saved_query", query=case.query)
    await saved_query.save(db=db)
    token = generate_access_token(account_id=account.id, session_id=uuid4())
    match case.credential:
        case "api":
            headers = [(b"x-infrahub-key", b"admin-security")]
        case "bearer":
            headers = [(b"authorization", f"Bearer {token}".encode())]
        case "cookie":
            headers = [(b"cookie", f"access_token={token}".encode())]
        case "invalid_api":
            headers = [(b"x-infrahub-key", b"invalid")]
        case "invalid_bearer":
            headers = [(b"authorization", b"Bearer invalid")]
        case "expired":
            expired_token = jwt.encode(
                {"sub": account.id, "session_id": str(uuid4()), "type": "access", "exp": 0},
                config.SETTINGS.security.secret_key,
                algorithm="HS256",
            )
            headers = [(b"authorization", f"Bearer {expired_token}".encode())]
        case "api_precedence":
            headers = [(b"x-infrahub-key", b"admin-security"), (b"cookie", b"access_token=invalid")]
        case "bearer_precedence":
            headers = [(b"authorization", b"Bearer invalid"), (b"cookie", f"access_token={token}".encode())]
        case "none":
            headers = []

    async with _websocket_messages(db=db, headers=headers, interval=1) as outgoing:
        handshake = await outgoing.get()
        if case.expected == "closed":
            assert handshake["type"] == "websocket.close"
            assert handshake["code"] == 4401
            return
        assert handshake["type"] == "websocket.accept"
        message = await outgoing.get()
        assert message["type"] == "websocket.send"
        payload = json.loads(message["text"])["payload"]
        if case.expected == "denied":
            assert "data" not in payload
            assert payload["errors"][0]["extensions"]["code"] == "PERMISSION_DENIED"
        elif case.query == TAG_QUERY:
            assert payload == {
                "data": {"query": {"BuiltinTag": {"edges": [{"node": {"name": {"value": "visible-tag"}}}]}}}
            }
        else:
            assert payload == {"data": {"query": {"InfrahubAccountToken": {"count": 1}}}}
        if case.disable_anonymous_after_result:
            monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", False)
            message = await outgoing.get()
            payload = json.loads(message["text"])["payload"]
            assert "data" not in payload
            assert payload["errors"][0]["message"] == "Authentication is required to perform this operation"


@pytest.mark.parametrize("revocation", ["secret_key_rotated", "account_deactivated"])
async def test_saved_query_subscription_ends_when_credentials_are_revoked(
    db: InfrahubDatabase,
    create_test_admin: Node,
    default_permission_backend: None,
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", False)
    tag = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag.new(db=db, name="visible-tag")
    await tag.save(db=db)
    saved_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await saved_query.new(db=db, name="saved_query", query=TAG_QUERY)
    await saved_query.save(db=db)
    if revocation == "secret_key_rotated":
        token = generate_access_token(account_id=create_test_admin.id, session_id=uuid4())
        headers = [(b"authorization", f"Bearer {token}".encode())]
        expected_error = "Invalid token"
    else:
        headers = [(b"x-infrahub-key", b"admin-security")]
        expected_error = "This account has been deactivated"

    async with _websocket_messages(db=db, headers=headers, interval=1) as outgoing:
        assert (await outgoing.get())["type"] == "websocket.accept"
        assert "data" in json.loads((await outgoing.get())["text"])["payload"]

        if revocation == "secret_key_rotated":
            monkeypatch.setattr(config.SETTINGS.security, "secret_key", "rotated-secret-key")
        else:
            create_test_admin.status.value = AccountStatus.INACTIVE.value
            await create_test_admin.save(db=db)

        payload = json.loads((await outgoing.get())["text"])["payload"]
        while "data" in payload:
            payload = json.loads((await outgoing.get())["text"])["payload"]
        assert payload["errors"][0]["message"] == expected_error
