from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrahub.webhook.query import KeyValueWebhookResult
from infrahub.webhook.tasks.invalidate import invalidate_webhook_headers

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

LOGGER_NAME = "infrahub.webhook.tasks.invalidate"


def _mock_database_with_session() -> tuple[MagicMock, AsyncMock]:
    """Create a mock database that supports `async with database.start_session()`."""
    mock_db = MagicMock()
    mock_session = AsyncMock()

    @asynccontextmanager
    async def _start_session(**kwargs: Any) -> AsyncGenerator[AsyncMock]:
        yield mock_session

    mock_db.start_session = _start_session
    return mock_db, mock_session


@pytest.fixture(autouse=True)
def _patch_prefect_logger() -> Any:
    """Replace Prefect's get_run_logger with a standard logger so caplog captures output."""
    with patch(
        "infrahub.webhook.tasks.invalidate.get_run_logger",
        return_value=logging.getLogger(LOGGER_NAME),
    ):
        yield


async def test_skips_when_no_event_data(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await invalidate_webhook_headers.fn(event_type=None, event_data=None)

    assert "No KeyValue ID provided, skipping" in caplog.text


async def test_skips_when_no_node_id_in_event_data(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await invalidate_webhook_headers.fn(event_type="infrahub.node.updated", event_data={"node_id": None})

    assert "No KeyValue ID provided, skipping" in caplog.text


@patch("infrahub.webhook.tasks.invalidate.invalidate_webhook_cache", new_callable=AsyncMock)
@patch("infrahub.webhook.tasks.invalidate.KeyValueGetWebhooksQuery")
@patch("infrahub.webhook.tasks.invalidate.get_database")
async def test_invalidates_when_webhooks_found(
    mock_get_database: AsyncMock,
    mock_query_cls: MagicMock,
    mock_invalidate: AsyncMock,
) -> None:
    mock_db, _mock_session = _mock_database_with_session()
    mock_get_database.return_value = mock_db

    mock_query = MagicMock()
    mock_query.get_data.return_value = KeyValueWebhookResult(webhook_uuids=frozenset({"wh-1", "wh-2"}))
    mock_query.execute = AsyncMock()
    mock_query_cls.init = AsyncMock(return_value=mock_query)

    await invalidate_webhook_headers.fn(
        event_type="infrahub.node.updated",
        event_data={"node_id": "kv-123"},
    )

    mock_invalidate.assert_awaited_once_with(webhook_ids=frozenset({"wh-1", "wh-2"}))


@patch("infrahub.webhook.tasks.invalidate.invalidate_webhook_cache", new_callable=AsyncMock)
@patch("infrahub.webhook.tasks.invalidate.KeyValueGetWebhooksQuery")
@patch("infrahub.webhook.tasks.invalidate.get_database")
async def test_logs_when_no_webhooks_found(
    mock_get_database: AsyncMock,
    mock_query_cls: MagicMock,
    mock_invalidate: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_db, _mock_session = _mock_database_with_session()
    mock_get_database.return_value = mock_db

    mock_query = MagicMock()
    mock_query.get_data.return_value = KeyValueWebhookResult(webhook_uuids=frozenset())
    mock_query.execute = AsyncMock()
    mock_query_cls.init = AsyncMock(return_value=mock_query)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await invalidate_webhook_headers.fn(
            event_type="infrahub.node.updated",
            event_data={"node_id": "kv-456"},
        )

    mock_invalidate.assert_not_awaited()
    assert "No webhooks reference KeyValue kv-456" in caplog.text
