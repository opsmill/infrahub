from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from neo4j.exceptions import ClientError, TransientError

from infrahub import config
from infrahub.database import retry_db_transaction
from infrahub.database.metrics import TRANSACTION_RETRIES

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def _set_retry_limit() -> Generator[None, None, None]:
    original_retry_limit = config.SETTINGS.database.retry_limit
    original_base_delay = config.SETTINGS.database.retry_base_delay
    original_max_delay = config.SETTINGS.database.retry_max_delay
    original_jitter_max = config.SETTINGS.database.retry_jitter_max

    config.SETTINGS.database.retry_limit = 3
    config.SETTINGS.database.retry_base_delay = 0.1
    config.SETTINGS.database.retry_max_delay = 2.0
    config.SETTINGS.database.retry_jitter_max = 0.0
    yield
    config.SETTINGS.database.retry_limit = original_retry_limit
    config.SETTINGS.database.retry_base_delay = original_base_delay
    config.SETTINGS.database.retry_max_delay = original_max_delay
    config.SETTINGS.database.retry_jitter_max = original_jitter_max


@pytest.fixture
def _set_high_retry_limit() -> Generator[None, None, None]:
    original = config.SETTINGS.database.retry_limit
    config.SETTINGS.database.retry_limit = 20
    yield
    config.SETTINGS.database.retry_limit = original


def _make_transient_error(message: str = "pool exhausted") -> TransientError:
    return TransientError(message)


def _make_client_error(
    message: str = "not found", code: str = "Neo.ClientError.Statement.EntityNotFound"
) -> ClientError:
    exc = ClientError(message)
    parts = code.split(".")
    exc._neo4j_code = code
    exc._classification = parts[1] if len(parts) > 1 else ""
    exc._category = parts[2] if len(parts) > 2 else ""
    exc._title = parts[3] if len(parts) > 3 else ""
    return exc


@pytest.mark.usefixtures("_set_retry_limit")
class TestRetryDbTransactionExponentialBackoff:
    async def test_no_error_no_retry(self) -> None:
        mock_fn = AsyncMock(return_value="ok")
        decorated = retry_db_transaction(name="test_no_retry")(mock_fn)

        result = await decorated()

        assert result == "ok"
        assert mock_fn.call_count == 1

    async def test_transient_error_triggers_retry(self) -> None:
        mock_fn = AsyncMock(side_effect=[_make_transient_error(), "ok"])
        decorated = retry_db_transaction(name="test_transient")(mock_fn)

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            result = await decorated()

        assert result == "ok"
        assert mock_fn.call_count == 2

    async def test_client_error_entity_not_found_triggers_retry(self) -> None:
        mock_fn = AsyncMock(side_effect=[_make_client_error(code="Neo.ClientError.Statement.EntityNotFound"), "ok"])
        decorated = retry_db_transaction(name="test_entity_not_found")(mock_fn)

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            result = await decorated()

        assert result == "ok"
        assert mock_fn.call_count == 2

    async def test_client_error_other_code_raises_immediately(self) -> None:
        other_error = _make_client_error(message="syntax error", code="Neo.ClientError.Statement.SyntaxError")
        mock_fn = AsyncMock(side_effect=[other_error])
        decorated = retry_db_transaction(name="test_other_client_error")(mock_fn)

        with pytest.raises(ClientError, match="syntax error"):
            await decorated()

        assert mock_fn.call_count == 1

    async def test_retry_exhaustion_raises_final_error(self) -> None:
        errors = [_make_transient_error(f"error {i}") for i in range(3)]
        mock_fn = AsyncMock(side_effect=errors)
        decorated = retry_db_transaction(name="test_exhaustion")(mock_fn)

        with patch.object(asyncio, "sleep", new_callable=AsyncMock), pytest.raises(TransientError):
            await decorated()

        assert mock_fn.call_count == 3

    async def test_exponential_backoff_timing(self) -> None:
        errors = [_make_transient_error(f"error {i}") for i in range(3)]
        mock_fn = AsyncMock(side_effect=errors)
        decorated = retry_db_transaction(name="test_backoff")(mock_fn)

        sleep_mock = AsyncMock()
        with (
            patch.object(asyncio, "sleep", sleep_mock),
            patch("infrahub.database.random.uniform", return_value=0.0),
            pytest.raises(TransientError),
        ):
            await decorated()

        # With jitter=0: attempt 1 -> 0.1 * 2^0 = 0.1, attempt 2 -> 0.1 * 2^1 = 0.2
        # attempt 3 is the last so it breaks after incrementing metrics
        assert sleep_mock.call_count == 3
        delays = [call.args[0] for call in sleep_mock.call_args_list]
        assert abs(delays[0] - 0.1) < 0.001
        assert abs(delays[1] - 0.2) < 0.001
        assert abs(delays[2] - 0.4) < 0.001

    @pytest.mark.usefixtures("_set_high_retry_limit")
    async def test_max_delay_cap(self) -> None:
        errors = [_make_transient_error(f"error {i}") for i in range(20)]
        mock_fn = AsyncMock(side_effect=errors)
        decorated = retry_db_transaction(name="test_max_delay")(mock_fn)

        sleep_mock = AsyncMock()
        with (
            patch.object(asyncio, "sleep", sleep_mock),
            patch("infrahub.database.random.uniform", return_value=0.0),
            pytest.raises(TransientError),
        ):
            await decorated()

        delays = [call.args[0] for call in sleep_mock.call_args_list]
        for delay in delays:
            assert delay <= 2.0

    async def test_transaction_retries_metric_incremented(self) -> None:
        metric_name = "test_metric_increment"
        initial_value = TRANSACTION_RETRIES.labels(metric_name)._value.get()

        mock_fn = AsyncMock(side_effect=[_make_transient_error(), "ok"])
        decorated = retry_db_transaction(name=metric_name)(mock_fn)

        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            await decorated()

        new_value = TRANSACTION_RETRIES.labels(metric_name)._value.get()
        assert new_value == initial_value + 1

    async def test_functools_wraps_preserves_metadata(self) -> None:
        async def my_original_function() -> str:
            """My docstring."""
            return "ok"

        decorated = retry_db_transaction(name="test_wraps")(my_original_function)
        assert decorated.__name__ == "my_original_function"  # type: ignore[attr-defined]
        assert decorated.__doc__ == "My docstring."  # type: ignore[attr-defined]
