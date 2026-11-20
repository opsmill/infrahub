"""The memory one process holds to encrypt stored objects stays under the configured number of bytes."""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import HTTPException

from infrahub import config
from infrahub.api.storage import encryption_migration
from infrahub.api.storage.encryption_migration import (
    EncryptBatchRequest,
    encrypt_stored_object_route,
    encrypt_stored_objects_route,
)
from infrahub.config import FileSystemStorageSettings, StorageSettings
from infrahub.core.registry import registry
from infrahub.storage import InfrahubObjectStorage
from infrahub.storage_encryption import migrate
from infrahub.storage_encryption.crypto import StorageKey
from infrahub.storage_encryption.memory_budget import (
    MEMORY_FACTOR,
    MemoryBudget,
    MemoryBudgetBusyError,
    ProcessMemoryBudget,
)
from infrahub.storage_encryption.migrate import EncryptOutcome, encrypt_object
from tests.helpers.route_caller import CALLER_ACCOUNT, CALLER_REQUEST

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

KEY = StorageKey.derive("memory-budget-test-secret-key-0123456789abcdef")
FILE_SIZE = 100
FILE_ONE = "18a3f2e4-0000-4b1e-a0f7-3c9d2b6e8f01"
FILE_TWO = "18a3f2e4-0000-4b1e-a0f7-3c9d2b6e8f02"
BYTES_PER_MEGABYTE = 100
"""The route turns megabytes into bytes with this factor, which these tests set to 100 to use small files."""
BUDGET_MB = 7
"""700 bytes: a file of 100 bytes takes 300, so two fit and three do not."""


def md5_of(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


def file_of(letter: str, size: int = FILE_SIZE) -> bytes:
    return letter.encode() * size


class HoldRecordingStorage(InfrahubObjectStorage):
    """A local storage that records which objects are in memory: from the end of their read to their replacement."""

    def __init__(self, settings: StorageSettings, key: StorageKey, meet_at: int = 0) -> None:
        super().__init__(settings=settings, key=key)
        self.in_memory: dict[str, int] = {}
        self.peak_bytes = 0
        self.reads: list[str] = []
        self._lock = threading.Lock()
        self._meeting = threading.Barrier(meet_at, timeout=5) if meet_at else None

    def read_stored_bounded(
        self, identifier: str, max_size: int, before_read: Callable[[int], None] | None = None
    ) -> tuple[int, bytes | None] | None:
        stored = super().read_stored_bounded(identifier=identifier, max_size=max_size, before_read=before_read)
        if stored is not None and stored[1] is not None:
            with self._lock:
                self.reads.append(identifier)
                self.in_memory[identifier] = stored[0]
                self.peak_bytes = max(self.peak_bytes, sum(self.in_memory.values()))
        return stored

    def replace(self, identifier: str, content: bytes) -> None:
        if self._meeting is not None:
            # Holds the objects in memory together, so the test fails when the budget keeps them apart.
            self._meeting.wait()
        else:
            time.sleep(0.05)
        super().replace(identifier=identifier, content=content)
        with self._lock:
            self.in_memory.pop(identifier, None)


def build_storage(path: Path, meet_at: int = 0) -> HoldRecordingStorage:
    path.mkdir(parents=True, exist_ok=True)
    return HoldRecordingStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": path}), encryption_enabled=True
        ),
        key=KEY,
        meet_at=meet_at,
    )


def store(storage: HoldRecordingStorage, root: Path, files: dict[str, bytes]) -> None:
    for identifier, content in files.items():
        (root / identifier).write_bytes(content)


async def encrypt_in_threads(
    storage: HoldRecordingStorage, budget: MemoryBudget, files: dict[str, bytes], wait_seconds: float
) -> dict[str, EncryptOutcome]:
    results = await asyncio.gather(
        *(
            asyncio.to_thread(
                encrypt_object,
                storage,
                identifier,
                frozenset({md5_of(content)}),
                1_000_000,
                budget,
                wait_seconds,
            )
            for identifier, content in files.items()
        )
    )
    return {result.identifier: result.outcome for result in results}


@dataclass
class OverlapCase:
    name: str
    capacity: int
    meet_at: int
    """Number of objects the storage keeps in memory together before it writes any, or 0 for none."""
    expected_peak_bytes: int


OVERLAP_CASES = [
    OverlapCase(
        name="two_files_that_do_not_fit_together_are_held_one_after_the_other",
        capacity=MEMORY_FACTOR * FILE_SIZE + 50,
        meet_at=0,
        expected_peak_bytes=FILE_SIZE,
    ),
    OverlapCase(
        name="two_files_that_fit_together_are_held_together",
        capacity=2 * MEMORY_FACTOR * FILE_SIZE,
        meet_at=2,
        expected_peak_bytes=2 * FILE_SIZE,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in OVERLAP_CASES])
async def test_objects_in_memory_never_need_more_than_the_budget(case: OverlapCase, tmp_path: Path) -> None:
    files = {FILE_ONE: file_of("a"), FILE_TWO: file_of("b")}
    storage = build_storage(tmp_path, meet_at=case.meet_at)
    store(storage, tmp_path, files)

    outcomes = await encrypt_in_threads(storage, MemoryBudget(capacity=case.capacity), files, wait_seconds=10)

    assert outcomes == {FILE_ONE: EncryptOutcome.ENCRYPTED, FILE_TWO: EncryptOutcome.ENCRYPTED}
    assert storage.peak_bytes == case.expected_peak_bytes
    assert storage.in_memory == {}


async def test_a_small_file_is_encrypted_at_once_while_a_large_one_holds_most_of_the_memory(tmp_path: Path) -> None:
    budget = MemoryBudget(capacity=10 * MEMORY_FACTOR * FILE_SIZE)
    held = budget.claim(size=8 * FILE_SIZE, wait_seconds=0)
    storage = build_storage(tmp_path)
    store(storage, tmp_path, {FILE_ONE: file_of("a")})

    outcomes = await encrypt_in_threads(storage, budget, {FILE_ONE: file_of("a")}, wait_seconds=0)

    assert outcomes == {FILE_ONE: EncryptOutcome.ENCRYPTED}
    budget.release(held)


async def test_a_file_that_does_not_fit_in_the_free_memory_is_not_read(tmp_path: Path) -> None:
    budget = MemoryBudget(capacity=10 * MEMORY_FACTOR * FILE_SIZE)
    held = budget.claim(size=9 * FILE_SIZE + 50, wait_seconds=0)
    storage = build_storage(tmp_path)
    store(storage, tmp_path, {FILE_ONE: file_of("a")})

    with pytest.raises(MemoryBudgetBusyError, match=r"^300 bytes of the 3000 bytes of encryption memory are not free$"):
        await encrypt_in_threads(storage, budget, {FILE_ONE: file_of("a")}, wait_seconds=0)

    assert (storage.reads, (tmp_path / FILE_ONE).read_bytes()) == ([], file_of("a"))
    budget.release(held)


async def test_a_file_waits_for_memory_that_another_file_gives_back(tmp_path: Path) -> None:
    budget = MemoryBudget(capacity=MEMORY_FACTOR * FILE_SIZE)
    held = budget.claim(size=FILE_SIZE, wait_seconds=0)
    storage = build_storage(tmp_path)
    store(storage, tmp_path, {FILE_ONE: file_of("a")})

    waiting = asyncio.create_task(encrypt_in_threads(storage, budget, {FILE_ONE: file_of("a")}, wait_seconds=10))
    await asyncio.sleep(0.05)
    assert storage.reads == []
    budget.release(held)

    assert await waiting == {FILE_ONE: EncryptOutcome.ENCRYPTED}


async def test_a_file_larger_than_a_third_of_the_budget_is_skipped_without_being_read(tmp_path: Path) -> None:
    storage = build_storage(tmp_path)
    store(storage, tmp_path, {FILE_ONE: file_of("a", size=FILE_SIZE + 1)})

    result = await asyncio.to_thread(
        encrypt_object,
        storage,
        FILE_ONE,
        frozenset(),
        1_000_000,
        MemoryBudget(capacity=MEMORY_FACTOR * FILE_SIZE),
        0,
        True,
    )

    assert (result.outcome, result.size, result.reason, storage.reads) == (
        EncryptOutcome.SKIPPED_TOO_LARGE,
        FILE_SIZE + 1,
        f"{FILE_SIZE + 1} bytes is more than the limit of {FILE_SIZE} bytes",
        [],
    )


def test_the_memory_of_a_file_is_given_back_when_its_encryption_fails() -> None:
    budget = MemoryBudget(capacity=MEMORY_FACTOR * FILE_SIZE)

    def fail_while_holding() -> None:
        with budget.holding(wait_seconds=0) as hold:
            hold.take(FILE_SIZE)
            raise OSError("disk failure")

    with pytest.raises(OSError, match=r"^disk failure$"):
        fail_while_holding()

    assert budget.claim(size=FILE_SIZE, wait_seconds=0) == MEMORY_FACTOR * FILE_SIZE


def test_a_hold_takes_memory_once() -> None:
    budget = MemoryBudget(capacity=10 * FILE_SIZE)

    with budget.holding(wait_seconds=0) as hold:
        hold.take(FILE_SIZE)
        with pytest.raises(RuntimeError, match=r"^This hold already took its memory$"):
            hold.take(FILE_SIZE)


def test_an_object_that_could_never_fit_is_refused_at_once() -> None:
    budget = MemoryBudget(capacity=MEMORY_FACTOR * FILE_SIZE)

    with pytest.raises(ValueError, match=r"^An object of 101 bytes needs 303 bytes, more than the budget of 300$"):
        budget.claim(size=FILE_SIZE + 1, wait_seconds=0)


# ----------------------------------------------------------------------------------------------------------
# The routes
# ----------------------------------------------------------------------------------------------------------
class AllowAll:
    def raise_for_permission(self, permission: object, message: str = "") -> None:
        return None


@pytest.fixture(autouse=True)
def route_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config,
        "SETTINGS",
        SimpleNamespace(
            storage=SimpleNamespace(encryption_migration_max_size=1, encryption_migration_memory_budget=BUDGET_MB)
        ),
    )
    monkeypatch.setattr(encryption_migration, "BYTES_PER_MEGABYTE", BYTES_PER_MEGABYTE)
    monkeypatch.setattr(encryption_migration, "PROCESS_MEMORY_BUDGET", ProcessMemoryBudget())
    monkeypatch.setattr(encryption_migration, "MEMORY_WAIT_SECONDS", 0.01)
    monkeypatch.setattr(encryption_migration, "BATCH_MEMORY_WAIT_SECONDS", 0.01)

    async def checksums_of_many(db: Any, storage_ids: list[str]) -> dict[str, frozenset[str]]:
        return {storage_id: frozenset({md5_of(file_of("a"))}) for storage_id in storage_ids}

    monkeypatch.setattr(migrate, "get_recorded_checksums", checksums_of_many)


def use_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> HoldRecordingStorage:
    storage = build_storage(tmp_path)
    store(storage, tmp_path, {FILE_ONE: file_of("a")})
    monkeypatch.setattr(registry, "_storage", storage)
    return storage


NO_DATABASE: Any = None
ALLOW_ALL: Any = AllowAll()


async def call_single_route() -> list[EncryptOutcome]:
    response = await encrypt_stored_object_route(
        identifier=FILE_ONE,
        allow_unverified=False,
        db=NO_DATABASE,
        permission_manager=ALLOW_ALL,
        request=CALLER_REQUEST,
        account=CALLER_ACCOUNT,
    )
    return [response.outcome]


async def call_batch_route() -> list[EncryptOutcome]:
    response = await encrypt_stored_objects_route(
        request=EncryptBatchRequest(identifiers=[FILE_ONE]),
        db=NO_DATABASE,
        permission_manager=ALLOW_ALL,
        http_request=CALLER_REQUEST,
        account=CALLER_ACCOUNT,
    )
    return [result.outcome for result in response.results]


@pytest.mark.parametrize("call", [call_single_route, call_batch_route], ids=["single_route", "batch_route"])
async def test_a_route_answers_429_with_retry_after_when_the_memory_of_the_process_is_all_taken(
    call: Callable[[], Awaitable[list[EncryptOutcome]]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    storage = use_storage(monkeypatch, tmp_path)
    budget = encryption_migration.memory_budget()
    held = budget.claim(size=budget.largest_object, wait_seconds=0)

    with pytest.raises(HTTPException) as refused:
        await call()

    assert (refused.value.status_code, refused.value.headers, storage.reads, (tmp_path / FILE_ONE).read_bytes()) == (
        429,
        {"Retry-After": "1"},
        [],
        file_of("a"),
    )
    budget.release(held)


@pytest.mark.parametrize("call", [call_single_route, call_batch_route], ids=["single_route", "batch_route"])
async def test_a_route_encrypts_a_file_once_the_memory_is_free(
    call: Callable[[], Awaitable[list[EncryptOutcome]]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_storage(monkeypatch, tmp_path)
    budget = encryption_migration.memory_budget()
    held = budget.claim(size=budget.largest_object, wait_seconds=0)
    budget.release(held)

    assert await call() == [EncryptOutcome.ENCRYPTED]
    assert (tmp_path / FILE_ONE).read_bytes()[:4] == b"IHSE"
