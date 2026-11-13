from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest
from starlette.applications import Starlette

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.graphql.api.endpoints import router
from infrahub.graphql.app import subscription_tasks

if TYPE_CHECKING:
    from starlette.types import Message, Scope

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("path", ["/graphql", "/graphql/main"])
async def test_anonymous_websocket_cannot_execute_saved_query(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", False)
    saved_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await saved_query.new(db=db, name="tag_count", query="query { BuiltinTag { count } }")
    await saved_query.save(db=db)

    app = Starlette(routes=router.routes)
    app.state.db = db
    app.state.service = None
    incoming: asyncio.Queue[Message] = asyncio.Queue()
    outgoing: asyncio.Queue[Message] = asyncio.Queue()
    scope: Scope = {"type": "websocket", "path": path, "headers": [], "query_string": b""}
    incoming.put_nowait({"type": "websocket.connect"})
    incoming.put_nowait(
        {
            "type": "websocket.receive",
            "text": json.dumps(
                {"id": "1", "type": "start", "payload": {"query": 'subscription { query(name: "tag_count") }'}}
            ),
        }
    )
    previous_tasks = subscription_tasks.copy()
    task = asyncio.create_task(app(scope=scope, receive=incoming.get, send=outgoing.put))
    try:
        async with asyncio.timeout(10):
            response = await outgoing.get()
            if response["type"] == "websocket.accept":
                response = await outgoing.get()
        assert response["type"] == "websocket.close", response
        assert response["code"] == 4401
    finally:
        started_tasks = subscription_tasks - previous_tasks
        for subscription_task in started_tasks:
            subscription_task.cancel()
        await asyncio.gather(*started_tasks, return_exceptions=True)
        incoming.put_nowait({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(task, timeout=10)
