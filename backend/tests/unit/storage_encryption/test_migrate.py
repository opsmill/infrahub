from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import botocore.exceptions
import pytest
from structlog.testing import capture_logs

from infrahub.config import FileSystemStorageSettings, StorageSettings
from infrahub.exceptions import StorageEncryptionError
from infrahub.storage import InfrahubObjectStorage
from infrahub.storage_encryption.codec import StoredContent, select_codec
from infrahub.storage_encryption.crypto import StorageKey, seal
from infrahub.storage_encryption.memory_budget import MemoryBudget
from infrahub.storage_encryption.migrate import (
    EncryptOutcome,
    EncryptResult,
    encrypt_object,
    precheck_object,
    require_encryption_ready,
)
from infrahub.storage_encryption.status import HEADER_PEEK_LENGTH

if TYPE_CHECKING:
    from collections.abc import Callable, Collection
    from pathlib import Path

    from infrahub.storage_encryption.status import EncryptionCheck

KEY = StorageKey.derive("unit-test-secret-key-0123456789abcdef")
OTHER_KEY = StorageKey.derive("another-unit-test-secret-key-987654321")
IDENTIFIER = "18a3f2e4-5c3d-4b1e-a0f7-3c9d2b6e8f01"
CONTENT = b"hostname leaf01\ninterface Ethernet1\n  description uplink to spine01\n"
CONTENT_SIZE = 68
CONTENT_MD5 = "165603f7ee0da21a5b52bb643410ef96"
CONTENT_SHA1 = "6f5edee3ebccfb2867e48cd334fc3c2fa8da4cd1"
OTHER_MD5 = "0123456789abcdef0123456789abcdef"
MAX_SIZE = 1024


def build_storage(
    path: Path, *, encryption_enabled: bool = True, key: StorageKey | None = KEY
) -> InfrahubObjectStorage:
    return InfrahubObjectStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": path}), encryption_enabled=encryption_enabled
        ),
        codec=select_codec(encryption_enabled=encryption_enabled, key=key),
    )


def encrypt_checked(
    storage: InfrahubObjectStorage,
    identifier: str,
    checksums: Collection[str] | None,
    max_size: int,
    allow_unverified: bool = False,
) -> EncryptResult:
    """What the routes do for one object: the readiness check, the header check, then the encryption."""
    require_encryption_ready(storage=storage)
    return precheck_object(storage=storage, identifier=identifier) or encrypt_object(
        storage=storage,
        identifier=identifier,
        checksums=checksums,
        max_size=max_size,
        budget=MemoryBudget(capacity=10**9),
        wait_seconds=0,
        allow_unverified=allow_unverified,
    )


def test_pinned_digests_are_those_of_the_content() -> None:
    assert (
        hashlib.md5(CONTENT, usedforsecurity=False).hexdigest(),
        hashlib.sha1(CONTENT, usedforsecurity=False).hexdigest(),
        len(CONTENT),
    ) == (CONTENT_MD5, CONTENT_SHA1, CONTENT_SIZE)


@dataclass
class EncryptedCase:
    name: str
    checksums: frozenset[str] | None
    allow_unverified: bool


ENCRYPTED_CASES = [
    EncryptedCase(name="artifact_md5", checksums=frozenset({CONTENT_MD5}), allow_unverified=False),
    EncryptedCase(name="file_object_sha1", checksums=frozenset({CONTENT_SHA1}), allow_unverified=False),
    EncryptedCase(name="uppercase_checksum", checksums=frozenset({CONTENT_MD5.upper()}), allow_unverified=False),
    EncryptedCase(
        name="one_matching_among_several", checksums=frozenset({OTHER_MD5, CONTENT_MD5}), allow_unverified=False
    ),
    EncryptedCase(name="unknown_checksums_allowed", checksums=None, allow_unverified=True),
    EncryptedCase(name="no_checksum_allowed", checksums=frozenset(), allow_unverified=True),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in ENCRYPTED_CASES])
def test_verified_object_is_sealed_in_place_and_reads_back_authenticated(tmp_path: Path, case: EncryptedCase) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path)

    result = encrypt_checked(
        storage=storage,
        identifier=IDENTIFIER,
        checksums=case.checksums,
        max_size=MAX_SIZE,
        allow_unverified=case.allow_unverified,
    )

    stored = (tmp_path / IDENTIFIER).read_bytes()
    assert result == EncryptResult(identifier=IDENTIFIER, outcome=EncryptOutcome.ENCRYPTED, size=CONTENT_SIZE)
    assert stored[:13] == b"IHSE\x01" + bytes.fromhex(KEY.fingerprint)
    assert b"leaf01" not in stored
    assert storage.read(identifier=IDENTIFIER) == StoredContent(content=CONTENT, authenticated=True)
    assert [entry.name for entry in tmp_path.iterdir()] == [IDENTIFIER]


def test_second_call_leaves_the_encrypted_object_untouched(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path)
    encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)
    sealed_once = (tmp_path / IDENTIFIER).read_bytes()

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert result == EncryptResult(identifier=IDENTIFIER, outcome=EncryptOutcome.ALREADY_ENCRYPTED)
    assert (tmp_path / IDENTIFIER).read_bytes() == sealed_once


def test_already_encrypted_object_is_not_measured_against_the_size_limit(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(seal(identifier=IDENTIFIER, content=CONTENT, key=KEY))
    storage = build_storage(tmp_path)

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums=None, max_size=1)

    assert result == EncryptResult(identifier=IDENTIFIER, outcome=EncryptOutcome.ALREADY_ENCRYPTED)


@dataclass
class UntouchedCase:
    name: str
    stored: bytes
    checksums: frozenset[str] | None
    max_size: int
    expected: EncryptResult


UNTOUCHED_CASES = [
    UntouchedCase(
        name="checksum_mismatch",
        stored=CONTENT,
        checksums=frozenset({OTHER_MD5}),
        max_size=MAX_SIZE,
        expected=EncryptResult(
            identifier=IDENTIFIER,
            outcome=EncryptOutcome.SKIPPED_CHECKSUM_MISMATCH,
            size=CONTENT_SIZE,
            reason="the content matches none of the checksums recorded for it",
        ),
    ),
    UntouchedCase(
        name="no_recorded_checksum",
        stored=CONTENT,
        checksums=frozenset(),
        max_size=MAX_SIZE,
        expected=EncryptResult(
            identifier=IDENTIFIER,
            outcome=EncryptOutcome.SKIPPED_UNVERIFIED,
            size=CONTENT_SIZE,
            reason="no checksum is recorded for this object",
        ),
    ),
    UntouchedCase(
        name="unknown_checksums",
        stored=CONTENT,
        checksums=None,
        max_size=MAX_SIZE,
        expected=EncryptResult(
            identifier=IDENTIFIER,
            outcome=EncryptOutcome.SKIPPED_UNVERIFIED,
            size=CONTENT_SIZE,
            reason="no checksum is recorded for this object",
        ),
    ),
    UntouchedCase(
        name="checksum_of_an_unknown_algorithm",
        stored=CONTENT,
        checksums=frozenset({"abc123"}),
        max_size=MAX_SIZE,
        expected=EncryptResult(
            identifier=IDENTIFIER,
            outcome=EncryptOutcome.SKIPPED_UNVERIFIED,
            size=CONTENT_SIZE,
            reason="no checksum is recorded for this object",
        ),
    ),
    UntouchedCase(
        name="one_byte_over_the_limit",
        stored=CONTENT,
        checksums=frozenset({CONTENT_MD5}),
        max_size=CONTENT_SIZE - 1,
        expected=EncryptResult(
            identifier=IDENTIFIER,
            outcome=EncryptOutcome.SKIPPED_TOO_LARGE,
            size=CONTENT_SIZE,
            reason="68 bytes is more than the limit of 67 bytes",
        ),
    ),
    UntouchedCase(
        name="sealed_with_another_key",
        stored=seal(identifier=IDENTIFIER, content=CONTENT, key=OTHER_KEY),
        checksums=frozenset({CONTENT_MD5}),
        max_size=MAX_SIZE,
        expected=EncryptResult(
            identifier=IDENTIFIER,
            outcome=EncryptOutcome.FAILED,
            reason="the object starts like an encrypted one but is unreadable: unknown_key",
        ),
    ),
    UntouchedCase(
        name="truncated_envelope",
        stored=seal(identifier=IDENTIFIER, content=CONTENT, key=KEY)[:25],
        checksums=frozenset({CONTENT_MD5}),
        max_size=MAX_SIZE,
        expected=EncryptResult(
            identifier=IDENTIFIER,
            outcome=EncryptOutcome.FAILED,
            reason="the object starts like an encrypted one but is unreadable: truncated",
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in UNTOUCHED_CASES])
def test_object_that_is_not_encrypted_is_left_as_it_was(tmp_path: Path, case: UntouchedCase) -> None:
    (tmp_path / IDENTIFIER).write_bytes(case.stored)
    storage = build_storage(tmp_path)

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums=case.checksums, max_size=case.max_size)

    assert result == case.expected
    assert {entry.name: entry.read_bytes() for entry in tmp_path.iterdir()} == {IDENTIFIER: case.stored}


def test_object_at_the_size_limit_is_encrypted(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path)

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=CONTENT_SIZE)

    assert result == EncryptResult(identifier=IDENTIFIER, outcome=EncryptOutcome.ENCRYPTED, size=CONTENT_SIZE)


class ReadCountingStorage(InfrahubObjectStorage):
    """A storage that records each read of the content of an object."""

    def __init__(self, settings: StorageSettings, key: StorageKey | None = None) -> None:
        super().__init__(settings, codec=select_codec(encryption_enabled=settings.encryption_enabled, key=key))
        self.full_reads: list[str] = []

    def read_stored_bounded(
        self, identifier: str, max_size: int, before_read: Callable[[int], None] | None = None
    ) -> tuple[int, bytes | None] | None:
        stored = super().read_stored_bounded(identifier=identifier, max_size=max_size, before_read=before_read)
        if stored is not None and stored[1] is not None:
            self.full_reads.append(identifier)
        return stored


def build_read_counting_storage(path: Path) -> ReadCountingStorage:
    return ReadCountingStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": path}), encryption_enabled=True
        ),
        key=KEY,
    )


def test_too_large_object_is_never_read_in_full(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_read_counting_storage(tmp_path)

    too_large = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=10)
    reads_when_too_large = list(storage.full_reads)
    encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert too_large.outcome is EncryptOutcome.SKIPPED_TOO_LARGE
    assert (reads_when_too_large, storage.full_reads) == ([], [IDENTIFIER])


def test_missing_object_is_reported_and_nothing_is_created(tmp_path: Path) -> None:
    storage = build_storage(tmp_path)

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert result == EncryptResult(identifier=IDENTIFIER, outcome=EncryptOutcome.MISSING)
    assert list(tmp_path.iterdir()) == []


class FailingReplaceStorage(InfrahubObjectStorage):
    """A storage whose disk refuses every replacement."""

    def replace(self, identifier: str, content: bytes) -> None:
        raise OSError(28, "No space left on device")


def test_failed_replacement_is_reported_and_keeps_the_object(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = FailingReplaceStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": tmp_path}), encryption_enabled=True
        ),
        codec=select_codec(encryption_enabled=True, key=KEY),
    )

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert result == EncryptResult(
        identifier=IDENTIFIER,
        outcome=EncryptOutcome.FAILED,
        size=CONTENT_SIZE,
        reason="the object could not be replaced",
    )
    assert (tmp_path / IDENTIFIER).read_bytes() == CONTENT


def test_failed_replacement_logs_the_error_on_the_server_and_keeps_it_out_of_the_reason(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = FailingReplaceStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": tmp_path}), encryption_enabled=True
        ),
        codec=select_codec(encryption_enabled=True, key=KEY),
    )

    with capture_logs() as logged:
        result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert "No space left" not in str(result.reason)
    assert [(entry["log_level"], entry["identifier"], entry["error"]) for entry in logged] == [
        ("warning", IDENTIFIER, "[Errno 28] No space left on device")
    ]


class LostWriteStorage(InfrahubObjectStorage):
    """A storage that accepts a replacement and keeps the previous object."""

    def replace(self, identifier: str, content: bytes) -> None:
        return None


def test_object_that_does_not_read_back_encrypted_is_reported_as_failed(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = LostWriteStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": tmp_path}), encryption_enabled=True
        ),
        codec=select_codec(encryption_enabled=True, key=KEY),
    )

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert result == EncryptResult(
        identifier=IDENTIFIER,
        outcome=EncryptOutcome.FAILED,
        size=CONTENT_SIZE,
        reason="the object does not read back as encrypted after the write",
    )


def test_storage_without_a_key_is_refused_before_anything_is_read(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, key=None)

    with pytest.raises(
        StorageEncryptionError,
        match=(
            r"^Existing stored objects cannot be encrypted because this process has no storage key; run it where "
            r"INFRAHUB_STORAGE_ENCRYPTION_KEY or INFRAHUB_SECURITY_SECRET_KEY is set, as on the API server$"
        ),
    ):
        encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert (tmp_path / IDENTIFIER).read_bytes() == CONTENT


def test_storage_with_encryption_disabled_is_refused_even_with_a_key(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=False)

    with pytest.raises(
        StorageEncryptionError,
        match=(
            r"^Existing stored objects are not encrypted while storage encryption is disabled, because new files "
            r"would still be stored unencrypted; set INFRAHUB_STORAGE_ENCRYPTION_ENABLED to true first$"
        ),
    ):
        encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert (tmp_path / IDENTIFIER).read_bytes() == CONTENT


def test_ready_storage_gives_its_key(tmp_path: Path) -> None:
    assert require_encryption_ready(storage=build_storage(tmp_path)) is KEY


class BrokenStorage(InfrahubObjectStorage):
    """A storage whose network breaks in one step: the header read, the content read or the write."""

    def __init__(self, settings: StorageSettings, key: StorageKey | None, broken_step: str, error: Exception) -> None:
        super().__init__(settings, codec=select_codec(encryption_enabled=settings.encryption_enabled, key=key))
        self.broken_step = broken_step
        self.error = error

    def inspect_encryption(self, identifier: str, request_length: int = HEADER_PEEK_LENGTH) -> EncryptionCheck:
        if self.broken_step == "header":
            raise self.error
        return super().inspect_encryption(identifier=identifier, request_length=request_length)

    def read_stored_bounded(
        self, identifier: str, max_size: int, before_read: Callable[[int], None] | None = None
    ) -> tuple[int, bytes | None] | None:
        if self.broken_step == "read":
            raise self.error
        return super().read_stored_bounded(identifier=identifier, max_size=max_size, before_read=before_read)

    def replace(self, identifier: str, content: bytes) -> None:
        if self.broken_step == "write":
            raise self.error
        super().replace(identifier=identifier, content=content)


NETWORK_ERRORS = [
    pytest.param(botocore.exceptions.ResponseStreamingError(error="Connection broken"), id="response-streaming"),
    pytest.param(
        botocore.exceptions.ReadTimeoutError(endpoint_url="http://storage:3900", error="timed out"), id="read-timeout"
    ),
    pytest.param(botocore.exceptions.ConnectionClosedError(endpoint_url="http://storage:3900"), id="connection-closed"),
]


@pytest.mark.parametrize("error", NETWORK_ERRORS)
@pytest.mark.parametrize(
    ("broken_step", "reason"),
    [
        ("header", "the header could not be read"),
        ("read", "the object could not be read"),
        ("write", "the object could not be replaced"),
    ],
)
def test_network_error_of_the_storage_fails_the_object_and_not_the_request(
    tmp_path: Path, broken_step: str, reason: str, error: Exception
) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = BrokenStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": tmp_path}), encryption_enabled=True
        ),
        key=KEY,
        broken_step=broken_step,
        error=error,
    )

    result = encrypt_checked(storage=storage, identifier=IDENTIFIER, checksums={CONTENT_MD5}, max_size=MAX_SIZE)

    assert (result.outcome, result.reason) == (EncryptOutcome.FAILED, reason)
    assert (tmp_path / IDENTIFIER).read_bytes() == CONTENT
