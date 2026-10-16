from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ClientError, TransientError

from infrahub import config, lock
from infrahub.database import (
    InfrahubDatabase,
    InfrahubDatabaseMode,
    retry_db_transaction,
    run_in_transaction_with_retry,
    run_with_retry,
)
from infrahub.database.metrics import TRANSACTION_RETRIES

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from types import TracebackType

    from neo4j import AsyncDriver
    from typing_extensions import Self


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


@pytest.fixture
def _set_zero_delay_retries() -> Generator[None, None, None]:
    original_retry_limit = config.SETTINGS.database.retry_limit
    original_base_delay = config.SETTINGS.database.retry_base_delay
    original_jitter_max = config.SETTINGS.database.retry_jitter_max

    config.SETTINGS.database.retry_limit = 3
    config.SETTINGS.database.retry_base_delay = 0.0
    config.SETTINGS.database.retry_jitter_max = 0.0
    yield
    config.SETTINGS.database.retry_limit = original_retry_limit
    config.SETTINGS.database.retry_base_delay = original_base_delay
    config.SETTINGS.database.retry_jitter_max = original_jitter_max


@pytest.fixture
async def neo4j_driver() -> AsyncGenerator[AsyncDriver, None]:
    """A driver that is never asked to run a query, so it never opens a connection."""
    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "unused"))
    yield driver
    await driver.close()


@pytest.fixture
def transaction_mode_db(neo4j_driver: AsyncDriver) -> InfrahubDatabase:
    """A database in transaction mode, standing in for one a caller opened and owns."""
    return InfrahubDatabase(driver=neo4j_driver, mode=InfrahubDatabaseMode.TRANSACTION)


@pytest.fixture
def driver_mode_db(neo4j_driver: AsyncDriver) -> InfrahubDatabase:
    """A database outside any transaction, as a mutation holds it before it opens one."""
    return InfrahubDatabase(driver=neo4j_driver, mode=InfrahubDatabaseMode.DRIVER)


class _RetriableWork:
    """Async callable that fails with a retriable error a fixed number of times, then succeeds."""

    def __init__(self, failures: int) -> None:
        self._failures = failures
        self.calls = 0

    async def run(self) -> str:
        self.calls += 1
        if self.calls <= self._failures:
            raise _make_transient_error("no available threads to serve this request")
        return "ok"


@pytest.mark.usefixtures("_set_zero_delay_retries")
class TestRetryOwnership:
    """Only the outermost retry scope replays.

    Layers that each retried independently multiplied into `retry_limit` raised to their nesting
    depth, which piles attempts onto a database already reporting that it cannot serve them.
    """

    async def test_nested_scopes_share_one_budget_of_attempts(self) -> None:
        work = _RetriableWork(failures=99)
        inner = retry_db_transaction(name="nested_inner")(work.run)
        outer = retry_db_transaction(name="nested_outer")(inner)

        with pytest.raises(TransientError, match=r"^no available threads to serve this request$"):
            await outer()

        assert work.calls == 3

    async def test_inner_scope_hands_the_error_to_the_owner(self) -> None:
        work = _RetriableWork(failures=1)
        inner = retry_db_transaction(name="handoff_inner")(work.run)
        outer = retry_db_transaction(name="handoff_outer")(inner)

        assert await outer() == "ok"
        assert work.calls == 2

    async def test_one_failure_is_counted_once_under_the_owning_label(self) -> None:
        inner_before = TRANSACTION_RETRIES.labels("counted_inner")._value.get()
        outer_before = TRANSACTION_RETRIES.labels("counted_outer")._value.get()

        work = _RetriableWork(failures=1)
        inner = retry_db_transaction(name="counted_inner")(work.run)
        outer = retry_db_transaction(name="counted_outer")(inner)

        assert await outer() == "ok"

        assert TRANSACTION_RETRIES.labels("counted_inner")._value.get() == inner_before
        assert TRANSACTION_RETRIES.labels("counted_outer")._value.get() == outer_before + 1

    async def test_a_task_awaited_inside_the_scope_shares_the_budget(self) -> None:
        work = _RetriableWork(failures=99)

        async def inner_task() -> str:
            return await retry_db_transaction(name="awaited_inner")(work.run)()

        async def spawn_and_await() -> str:
            return await asyncio.create_task(inner_task())

        with pytest.raises(TransientError, match=r"^no available threads to serve this request$"):
            await retry_db_transaction(name="awaited_outer")(spawn_and_await)()

        assert work.calls == 3

    async def test_a_task_outliving_the_scope_retries_on_its_own(self) -> None:
        """A scope must not leave the tasks it started unable to retry for the rest of their lives.

        Starting a task copies the context the claim lives in, and the copy is not the one the
        scope goes on to restore when it returns.
        """
        work = _RetriableWork(failures=1)
        scope_returned = asyncio.Event()

        async def retry_once_the_scope_is_gone() -> str:
            await scope_returned.wait()
            return await retry_db_transaction(name="outliving_task")(work.run)()

        async def spawn_only() -> asyncio.Task[str]:
            return asyncio.create_task(retry_once_the_scope_is_gone())

        task = await retry_db_transaction(name="spawning_scope")(spawn_only)()
        scope_returned.set()

        assert await task == "ok"
        assert work.calls == 2

    async def test_ownership_is_released_after_the_scope_returns(self) -> None:
        succeeding = _RetriableWork(failures=0)
        await retry_db_transaction(name="released_first")(succeeding.run)()

        later = _RetriableWork(failures=1)

        assert await retry_db_transaction(name="released_second")(later.run)() == "ok"
        assert later.calls == 2

    async def test_a_caller_owned_transaction_claims_the_retry(self, transaction_mode_db: InfrahubDatabase) -> None:
        """Entering a transaction the caller owns has to claim the retry as well as decline it.

        Replaying on that transaction can only raise a transaction-state error, so the failure has
        to reach the caller who is able to roll it back and open a new one.
        """
        work = _RetriableWork(failures=1)
        nested = retry_db_transaction(name="claimed_by_transaction_owner")(work.run)

        async def run_nested(_: InfrahubDatabase) -> str:
            return await nested()

        with pytest.raises(TransientError, match=r"^no available threads to serve this request$"):
            await run_in_transaction_with_retry(db=transaction_mode_db, name="transaction_owner", func=run_nested)

        assert work.calls == 1


@pytest.mark.usefixtures("_set_zero_delay_retries")
class TestRunWithRetry:
    """A mutation's reads are replayed as well as its write.

    An object is created from a schema, a template and a pool that are all read before the write
    transaction opens. A database saturated enough to fail those reads fails the mutation just as
    surely as one that fails the write, so both sides of it get the same second chance.
    """

    async def test_work_outside_a_transaction_is_replayed(self, driver_mode_db: InfrahubDatabase) -> None:
        work = _RetriableWork(failures=1)

        assert await run_with_retry(db=driver_mode_db, name="reads_before_the_write", func=work.run) == "ok"
        assert work.calls == 2

    async def test_a_caller_owned_transaction_is_not_replayed(self, transaction_mode_db: InfrahubDatabase) -> None:
        work = _RetriableWork(failures=1)

        with pytest.raises(TransientError, match=r"^no available threads to serve this request$"):
            await run_with_retry(db=transaction_mode_db, name="caller_owns_the_transaction", func=work.run)

        assert work.calls == 1

    async def test_an_enclosing_owner_keeps_the_whole_budget(self, driver_mode_db: InfrahubDatabase) -> None:
        work = _RetriableWork(failures=99)

        async def inner() -> str:
            return await run_with_retry(db=driver_mode_db, name="budget_inner", func=work.run)

        with pytest.raises(TransientError, match=r"^no available threads to serve this request$"):
            await retry_db_transaction(name="budget_outer")(inner)()

        assert work.calls == 3


class _RecordingLock:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    async def acquire(self) -> None:
        self.events.append(f"acquire:{self.name}")

    async def release(self) -> None:
        self.events.append(f"release:{self.name}")


class RecordingLockRegistry:
    """Stands in for the lock registry, recording every lock handed out and in what order."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.metrics_flags: list[bool] = []

    def get(self, name: str, metrics: bool = True) -> _RecordingLock:
        self.metrics_flags.append(metrics)
        return _RecordingLock(name=name, events=self.events)


class _RecordingTransaction(InfrahubDatabase):
    """A transaction that opens and commits against the recording list rather than a connection."""

    def __init__(self, driver: AsyncDriver, events: list[str]) -> None:
        super().__init__(driver=driver, mode=InfrahubDatabaseMode.TRANSACTION)
        self.events = events

    async def __aenter__(self) -> Self:
        self.events.append("transaction:open")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.events.append("transaction:close")


class _RecordingDatabase(InfrahubDatabase):
    """A database outside any transaction, whose transactions record instead of connecting."""

    def __init__(self, driver: AsyncDriver, events: list[str]) -> None:
        super().__init__(driver=driver, mode=InfrahubDatabaseMode.DRIVER)
        self.events = events

    def start_transaction(self, schemas: object | None = None) -> _RecordingTransaction:
        return _RecordingTransaction(driver=self._driver, events=self.events)


@pytest.fixture
def lock_events() -> list[str]:
    return []


@pytest.fixture
def recording_lock_registry(lock_events: list[str]) -> Generator[RecordingLockRegistry, None, None]:
    original = lock.registry
    registry = RecordingLockRegistry(events=lock_events)
    lock.registry = registry  # type: ignore[assignment]
    yield registry
    lock.registry = original


@pytest.fixture
def recording_db(neo4j_driver: AsyncDriver, lock_events: list[str]) -> _RecordingDatabase:
    return _RecordingDatabase(driver=neo4j_driver, events=lock_events)


@pytest.mark.usefixtures("_set_zero_delay_retries", "recording_lock_registry")
class TestRunInTransactionWithRetryLocks:
    """No lock is held across a backoff.

    Every attempt takes its locks, opens the transaction inside them, and gives both back before the
    next attempt sleeps. Holding a lock while waiting to retry would stall every other writer
    contending for the same object for the whole backoff sequence.
    """

    async def test_locks_are_taken_outside_the_transaction(
        self, recording_db: _RecordingDatabase, lock_events: list[str]
    ) -> None:
        async def work(_: InfrahubDatabase) -> str:
            lock_events.append("work")
            return "ok"

        result = await run_in_transaction_with_retry(
            db=recording_db, name="locked_create", func=work, lock_names=["outer", "inner"]
        )

        assert result == "ok"
        assert lock_events == [
            "acquire:outer",
            "acquire:inner",
            "transaction:open",
            "work",
            "transaction:close",
            "release:inner",
            "release:outer",
        ]

    async def test_every_attempt_takes_and_gives_back_its_locks(
        self, recording_db: _RecordingDatabase, lock_events: list[str]
    ) -> None:
        work = _RetriableWork(failures=2)

        async def attempt(_: InfrahubDatabase) -> str:
            return await work.run()

        result = await run_in_transaction_with_retry(
            db=recording_db, name="replayed_create", func=attempt, lock_names=["object"]
        )

        assert result == "ok"
        assert work.calls == 3
        assert (
            lock_events
            == [
                "acquire:object",
                "transaction:open",
                "transaction:close",
                "release:object",
            ]
            * 3
        )

    async def test_no_lock_is_taken_without_lock_names(
        self, recording_db: _RecordingDatabase, lock_events: list[str], recording_lock_registry: RecordingLockRegistry
    ) -> None:
        """The trigger-rule mutations name no lock, and an empty one still costs a context to enter."""

        async def work(_: InfrahubDatabase) -> str:
            lock_events.append("work")
            return "ok"

        result = await run_in_transaction_with_retry(db=recording_db, name="unlocked_create", func=work)

        assert result == "ok"
        assert recording_lock_registry.metrics_flags == []
        assert lock_events == ["transaction:open", "work", "transaction:close"]

    async def test_lock_metrics_are_off_unless_the_caller_asks(
        self, recording_db: _RecordingDatabase, recording_lock_registry: RecordingLockRegistry
    ) -> None:
        """The registry keeps one lock per name with the flag it was first built with."""

        async def work(_: InfrahubDatabase) -> str:
            return "ok"

        await run_in_transaction_with_retry(db=recording_db, name="default", func=work, lock_names=["quiet"])
        assert recording_lock_registry.metrics_flags == [False, False]

        await run_in_transaction_with_retry(
            db=recording_db, name="measured", func=work, lock_names=["loud"], metrics=True
        )
        assert recording_lock_registry.metrics_flags == [False, False, True, True]
