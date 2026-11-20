"""Every way a stored object is encrypted must refuse and encrypt the same objects.

Every case is run through every path of `PATHS` on its own storage, and the outcome and the stored files after the
call are compared with the ones of the shared function (`migrate.encrypt_stored_objects` with one identifier),
whose outcomes are also pinned in the cases. The recorded checksums come from a table, so these tests need no
database; the lookup of the checksums in the database is checked in
`backend/tests/component/api/test_64_storage_encryption_parity.py`.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import botocore.exceptions
import pytest
from fastapi import HTTPException

from infrahub import config
from infrahub.api.storage import encryption_migration
from infrahub.api.storage.encryption_migration import (
    EncryptBatchRequest,
    encrypt_stored_object_route,
    encrypt_stored_objects_route,
)
from infrahub.core.registry import registry
from infrahub.exceptions import StorageEncryptionError
from infrahub.storage import InfrahubObjectStorage, InfrahubS3ObjectStorage
from infrahub.storage_encryption import migrate
from infrahub.storage_encryption.crypto import StorageKey, seal
from infrahub.storage_encryption.memory_budget import MemoryBudget, ProcessMemoryBudget
from infrahub.storage_encryption.migrate import HEADER_REQUEST_LENGTH
from infrahub.storage_encryption.status import HEADER_PEEK_LENGTH

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

from infrahub.config import FileSystemStorageSettings, StorageSettings
from tests.helpers.route_caller import CALLER_ACCOUNT, CALLER_REQUEST

KEY = StorageKey.derive("parity-test-secret-key-0123456789abcdef")
OTHER_KEY = StorageKey.derive("another-parity-test-secret-key-987654321")
IDENTIFIER = "18a3f2e4-5c3d-4b1e-a0f7-3c9d2b6e8f01"
CONTENT = b"hostname leaf01\ninterface Ethernet1\n  description uplink to spine01\n"
CONTENT_MD5 = "165603f7ee0da21a5b52bb643410ef96"
CONTENT_SHA1 = "6f5edee3ebccfb2867e48cd334fc3c2fa8da4cd1"
EMPTY_MD5 = "d41d8cd98f00b204e9800998ecf8427e"
OTHER_MD5 = "0123456789abcdef0123456789abcdef"
LIMIT = 200
"""The size limit in bytes: the setting is in MB, and `BYTES_PER_MEGABYTE` is set to 200 for the tests."""
AT_LIMIT = b"a" * LIMIT
OVER_LIMIT = b"a" * (LIMIT + 1)
SEALED = seal(identifier=IDENTIFIER, content=CONTENT, key=KEY)
SEALED_OTHER_KEY = seal(identifier=IDENTIFIER, content=CONTENT, key=OTHER_KEY)
SEALED_TAMPERED = SEALED[:-1] + bytes([SEALED[-1] ^ 0xFF])
UNSUPPORTED_VERSION = b"IHSE\x07" + b"\x00" * 40
LYING_HEADER = b"\x00" * HEADER_PEEK_LENGTH

MEMORY_BUDGET_MB = 100
"""With the 200 bytes of a megabyte of these tests, a budget of 20,000 bytes holds many files of the limit."""
OTHER_IDENTIFIER = "28a3f2e4-5c3d-4b1e-a0f7-3c9d2b6e8f02"


def md5_of(content: bytes) -> str:
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


def read_files(root: Path) -> dict[str, bytes]:
    return {entry.name: entry.read_bytes() for entry in root.iterdir()}


def make_root(root: Path, stored: bytes | None) -> None:
    """Create the storage directory, holding the object under IDENTIFIER when there is one."""
    root.mkdir(parents=True, exist_ok=True)
    if stored is not None:
        (root / IDENTIFIER).write_bytes(stored)


def client_error(code: str, operation: str = "GetObject") -> botocore.exceptions.ClientError:
    return botocore.exceptions.ClientError(error_response={"Error": {"Code": code}}, operation_name=operation)


# ----------------------------------------------------------------------------------------------------------
# Storages
# ----------------------------------------------------------------------------------------------------------
def build_local_storage(
    path: Path, *, key: StorageKey | None = KEY, encryption_enabled: bool = True, cls: type = InfrahubObjectStorage
) -> InfrahubObjectStorage:
    return cls(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": path}), encryption_enabled=encryption_enabled
        ),
        key=key,
    )


class FailingReplaceStorage(InfrahubObjectStorage):
    """A storage whose disk refuses every replacement."""

    def replace(self, identifier: str, content: bytes) -> None:
        raise OSError(28, "No space left on device")


class LostWriteStorage(InfrahubObjectStorage):
    """A storage that accepts a replacement and keeps the previous object."""

    def replace(self, identifier: str, content: bytes) -> None:
        return None


class ChangingObjectStorage(InfrahubObjectStorage):
    """A storage that models another writer replacing the object between the header check and the read.

    Its header reads report a plain object until the first full read.
    """

    read_started = False

    def read_header(self, identifier: str, request_length: int = HEADER_PEEK_LENGTH) -> bytes | None:
        if self.read_started:
            return super().read_header(identifier=identifier, request_length=request_length)
        return LYING_HEADER

    def read_stored_bounded(
        self, identifier: str, max_size: int, before_read: Callable[[int], None] | None = None
    ) -> tuple[int, bytes | None] | None:
        self.read_started = True
        return super().read_stored_bounded(identifier=identifier, max_size=max_size, before_read=before_read)


class FakeS3Object:
    def __init__(self, bucket: FakeS3Bucket, name: str) -> None:
        self.bucket = bucket
        self.name = name

    def _data(self, operation: str) -> bytes:
        if self.name not in self.bucket.objects:
            raise client_error("NoSuchKey", operation)
        return self.bucket.objects[self.name]

    @property
    def content_length(self) -> int:
        self.bucket.calls.append(("size", None))
        if self.bucket.fail_on == "size":
            raise client_error("AccessDenied", "HeadObject")
        return len(self._data("HeadObject"))

    def get(self, Range: str | None = None) -> dict[str, Any]:  # noqa: N803
        data = self._data("GetObject")
        if Range is None:
            self.bucket.calls.append(("get", None))
            if self.bucket.fail_on == "read":
                raise client_error("AccessDenied")
            return {"Body": io.BytesIO(data), "ContentLength": len(data)}
        length = int(Range.removeprefix("bytes=0-")) + 1
        self.bucket.calls.append(("head", length))
        if not data:
            raise client_error("InvalidRange")
        return {"Body": io.BytesIO(data[:length]), "ContentLength": min(length, len(data))}

    def delete(self) -> None:
        self.bucket.objects.pop(self.name, None)


class FakeS3Bucket:
    """A bucket in memory that records the requests it receives and can refuse one kind of request."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, int | None]] = []
        self.fail_on: str | None = None

    def Object(self, name: str) -> FakeS3Object:  # noqa: N802
        return FakeS3Object(self, name)

    def download_fileobj(self, name: str, fileobj: io.BytesIO) -> None:
        self.calls.append(("download", None))
        if self.fail_on == "read":
            raise client_error("AccessDenied")
        if name not in self.objects:
            raise client_error("404", "HeadObject")
        fileobj.write(self.objects[name])

    def put_object(self, Key: str, Body: bytes, **kwargs: Any) -> None:  # noqa: N803
        self.calls.append(("put", len(Body)))
        if self.fail_on == "put":
            raise client_error("AccessDenied", "PutObject")
        self.objects[Key] = Body


class FakeS3Storage(InfrahubS3ObjectStorage):
    def __init__(self, bucket: FakeS3Bucket) -> None:
        self._bucket = bucket


def build_s3_storage(
    path: Path, bucket: FakeS3Bucket, *, key: StorageKey | None = KEY, encryption_enabled: bool = True
) -> InfrahubObjectStorage:
    storage = build_local_storage(path, key=key, encryption_enabled=encryption_enabled)
    storage._storage = FakeS3Storage(bucket)
    return storage


# ----------------------------------------------------------------------------------------------------------
# Paths: every way a stored object is encrypted, each returning the same description of what happened
# ----------------------------------------------------------------------------------------------------------
Described = tuple[Any, ...]


def describe_result(identifier: str, outcome: Any, size: int, reason: str | None) -> Described:
    return ("result", getattr(outcome, "value", outcome), size, reason)


def describe_error(error: Exception) -> Described:
    if isinstance(error, HTTPException):
        return ("error", error.status_code, error.detail)
    if isinstance(error, StorageEncryptionError):
        return ("error", 409, error.message)
    raise error


class AllowAll:
    """A permission manager that grants every permission."""

    def raise_for_permission(self, permission: object, message: str = "") -> None:
        return None


NO_DATABASE: Any = None
"""The checksums come from a table in these tests, so nothing reads the database."""
ALLOW_ALL: Any = AllowAll()


@dataclass
class Call:
    storage: InfrahubObjectStorage
    identifier: str
    allow_unverified: bool = False


async def call_function(call: Call) -> Described:
    (result,) = await migrate.encrypt_stored_objects(
        db=NO_DATABASE,
        storage=call.storage,
        identifiers=[call.identifier],
        max_size=LIMIT,
        budget=MemoryBudget(capacity=MEMORY_BUDGET_MB * LIMIT),
        wait_seconds=0.5,
        allow_unverified=call.allow_unverified,
    )
    return describe_result(result.identifier, result.outcome, result.size, result.reason)


async def call_route(call: Call) -> Described:
    response = await encrypt_stored_object_route(
        identifier=call.identifier,
        allow_unverified=call.allow_unverified,
        db=NO_DATABASE,
        permission_manager=ALLOW_ALL,
        request=CALLER_REQUEST,
        account=CALLER_ACCOUNT,
    )
    return describe_result(response.identifier, response.outcome, response.size, response.reason)


async def call_batch(call: Call) -> Described:
    response = await encrypt_stored_objects_route(
        request=EncryptBatchRequest(identifiers=[call.identifier], allow_unverified=call.allow_unverified),
        db=NO_DATABASE,
        permission_manager=ALLOW_ALL,
        http_request=CALLER_REQUEST,
        account=CALLER_ACCOUNT,
    )
    (result,) = response.results
    return describe_result(result.identifier, result.outcome, result.size, result.reason)


async def call_batch_with_neighbours(call: Call) -> Described:
    """The object is the middle one of a batch of three, the others being objects that need no work."""
    neighbours = ["00-neighbour-before", "zz-neighbour-after"]
    response = await encrypt_stored_objects_route(
        request=EncryptBatchRequest(
            identifiers=[neighbours[0], call.identifier, neighbours[1]], allow_unverified=call.allow_unverified
        ),
        db=NO_DATABASE,
        permission_manager=ALLOW_ALL,
        http_request=CALLER_REQUEST,
        account=CALLER_ACCOUNT,
    )
    (result,) = [entry for entry in response.results if entry.identifier == call.identifier]
    return describe_result(result.identifier, result.outcome, result.size, result.reason)


REFERENCE = "function"
PATHS: dict[str, Callable[[Call], Awaitable[Described]]] = {
    REFERENCE: call_function,
    "route": call_route,
    "batch": call_batch,
    "batch_with_neighbours": call_batch_with_neighbours,
}


@pytest.fixture(autouse=True)
def migration_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """A limit of 200 bytes per object and a memory budget that holds many objects of that size."""
    monkeypatch.setattr(
        config,
        "SETTINGS",
        SimpleNamespace(
            storage=SimpleNamespace(
                encryption_migration_max_size=1, encryption_migration_memory_budget=MEMORY_BUDGET_MB
            )
        ),
    )
    monkeypatch.setattr(encryption_migration, "BYTES_PER_MEGABYTE", LIMIT)
    monkeypatch.setattr(encryption_migration, "PROCESS_MEMORY_BUDGET", ProcessMemoryBudget())


@pytest.fixture
def recorded_checksums(monkeypatch: pytest.MonkeyPatch) -> dict[str, frozenset[str]]:
    """The checksums the database would return, by storage identifier."""
    table: dict[str, frozenset[str]] = {}

    async def lookup(db: Any, storage_ids: list[str]) -> dict[str, frozenset[str]]:
        return {storage_id: table.get(storage_id, frozenset()) for storage_id in storage_ids}

    monkeypatch.setattr(migrate, "get_recorded_checksums", lookup)
    return table


# ----------------------------------------------------------------------------------------------------------
# Cases
# ----------------------------------------------------------------------------------------------------------
@dataclass
class Case:
    name: str
    stored: bytes | None
    """What is stored under IDENTIFIER, or None when nothing is."""
    checksums: frozenset[str] = frozenset()
    allow_unverified: bool = False
    storage_cls: type = InfrahubObjectStorage
    key: StorageKey | None = KEY
    encryption_enabled: bool = True
    expected_outcome: str = ""
    """The outcome the shared function must give, so that a regression of the reference is also caught."""
    expected_encrypted: bool = False
    """Whether the object is encrypted afterwards."""


CASES = [
    Case(
        "md5_of_an_artifact", CONTENT, frozenset({CONTENT_MD5}), expected_outcome="encrypted", expected_encrypted=True
    ),
    Case(
        "sha1_of_a_file_object",
        CONTENT,
        frozenset({CONTENT_SHA1}),
        expected_outcome="encrypted",
        expected_encrypted=True,
    ),
    Case(
        "uppercase_checksum",
        CONTENT,
        frozenset({CONTENT_MD5.upper()}),
        expected_outcome="encrypted",
        expected_encrypted=True,
    ),
    Case(
        "one_matching_among_several",
        CONTENT,
        frozenset({OTHER_MD5, CONTENT_MD5}),
        expected_outcome="encrypted",
        expected_encrypted=True,
    ),
    Case(
        "empty_object_with_its_checksum",
        b"",
        frozenset({EMPTY_MD5}),
        expected_outcome="encrypted",
        expected_encrypted=True,
    ),
    Case("empty_object_without_checksum", b"", expected_outcome="skipped_unverified"),
    Case("checksum_mismatch", CONTENT, frozenset({OTHER_MD5}), expected_outcome="skipped_checksum_mismatch"),
    Case(
        "mismatch_even_when_unverified_is_allowed",
        CONTENT,
        frozenset({OTHER_MD5}),
        allow_unverified=True,
        expected_outcome="skipped_checksum_mismatch",
    ),
    Case("orphan_without_any_checksum", CONTENT, expected_outcome="skipped_unverified"),
    Case(
        "orphan_when_unverified_is_allowed",
        CONTENT,
        allow_unverified=True,
        expected_outcome="encrypted",
        expected_encrypted=True,
    ),
    Case("checksum_of_an_unknown_algorithm", CONTENT, frozenset({"abc123"}), expected_outcome="skipped_unverified"),
    Case(
        "at_the_size_limit",
        AT_LIMIT,
        frozenset({md5_of(AT_LIMIT)}),
        expected_outcome="encrypted",
        expected_encrypted=True,
    ),
    Case(
        "one_byte_over_the_size_limit",
        OVER_LIMIT,
        frozenset({md5_of(OVER_LIMIT)}),
        expected_outcome="skipped_too_large",
    ),
    Case("over_the_limit_and_orphan", OVER_LIMIT, expected_outcome="skipped_too_large"),
    Case("over_the_limit_and_mismatch", OVER_LIMIT, frozenset({OTHER_MD5}), expected_outcome="skipped_too_large"),
    Case("already_encrypted", SEALED, frozenset({CONTENT_MD5}), expected_outcome="already_encrypted"),
    Case("already_encrypted_without_checksum", SEALED, expected_outcome="already_encrypted"),
    Case(
        "already_encrypted_and_over_the_limit",
        seal(identifier=IDENTIFIER, content=OVER_LIMIT, key=KEY),
        expected_outcome="already_encrypted",
    ),
    Case(
        "already_encrypted_but_modified",
        SEALED_TAMPERED,
        frozenset({CONTENT_MD5}),
        expected_outcome="already_encrypted",
    ),
    Case("sealed_with_another_key", SEALED_OTHER_KEY, frozenset({CONTENT_MD5}), expected_outcome="failed"),
    Case("truncated_after_the_magic", SEALED[:4], frozenset({CONTENT_MD5}), expected_outcome="failed"),
    Case("truncated_inside_the_header", SEALED[:25], frozenset({CONTENT_MD5}), expected_outcome="failed"),
    Case("unsupported_format_version", UNSUPPORTED_VERSION, frozenset({CONTENT_MD5}), expected_outcome="failed"),
    Case("missing_object", None, frozenset({CONTENT_MD5}), expected_outcome="missing"),
    Case("missing_object_allowing_unverified", None, allow_unverified=True, expected_outcome="missing"),
    Case(
        "replacement_refused_by_the_disk",
        CONTENT,
        frozenset({CONTENT_MD5}),
        storage_cls=FailingReplaceStorage,
        expected_outcome="failed",
    ),
    Case(
        "replacement_that_does_not_read_back_encrypted",
        CONTENT,
        frozenset({CONTENT_MD5}),
        storage_cls=LostWriteStorage,
        expected_outcome="failed",
    ),
    Case(
        "object_encrypted_by_another_writer_during_the_call",
        SEALED,
        frozenset({CONTENT_MD5}),
        storage_cls=ChangingObjectStorage,
        expected_outcome="already_encrypted",
    ),
    Case(
        "object_sealed_with_another_key_during_the_call",
        SEALED_OTHER_KEY,
        frozenset({CONTENT_MD5}),
        storage_cls=ChangingObjectStorage,
        expected_outcome="failed",
    ),
]


def snapshot(storage: InfrahubObjectStorage, files: dict[str, bytes], originals: dict[str, bytes]) -> dict[str, Any]:
    """What the storage holds, with an object that was encrypted shown as its authenticated plain content."""
    state: dict[str, Any] = {}
    for name, data in sorted(files.items()):
        if originals.get(name) == data:
            state[name] = "unchanged"
            continue
        opened = storage.read(identifier=name)
        state[name] = ("replaced", opened.content, opened.authenticated, data[:4])
    return state


def prepare_local(case: Case, path: Path) -> tuple[InfrahubObjectStorage, Callable[[], dict[str, bytes]]]:
    make_root(path, case.stored)
    storage = build_local_storage(path, key=case.key, encryption_enabled=case.encryption_enabled, cls=case.storage_cls)
    return storage, lambda: read_files(path)


async def run_local_case(
    case: Case, path_name: str, root: Path, table: dict[str, frozenset[str]]
) -> tuple[Described, dict[str, Any]]:
    storage, files = prepare_local(case, root)
    originals = files()
    table[IDENTIFIER] = case.checksums
    registry._storage = storage
    try:
        described = await PATHS[path_name](
            Call(storage=storage, identifier=IDENTIFIER, allow_unverified=case.allow_unverified)
        )
    except (HTTPException, StorageEncryptionError) as error:
        described = describe_error(error)
    return described, snapshot(storage, files(), originals)


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CASES])
async def test_shared_function_gives_the_expected_outcome(
    case: Case, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    """The reference of the comparison below is itself pinned, so a change of the reference is noticed."""
    described, state = await run_local_case(case, REFERENCE, tmp_path / "ref", recorded_checksums)

    assert described[:2] == ("result", case.expected_outcome)
    expect_replaced = case.expected_encrypted
    assert [value != "unchanged" for value in state.values()] == ([expect_replaced] if case.stored is not None else [])
    if expect_replaced:
        assert state[IDENTIFIER][1:] == (case.stored, True, b"IHSE")


@pytest.mark.parametrize("path_name", [name for name in PATHS if name != REFERENCE])
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CASES])
async def test_every_path_gives_the_outcome_and_files_of_the_shared_function(
    case: Case, path_name: str, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    expected = await run_local_case(case, REFERENCE, tmp_path / "ref", recorded_checksums)

    actual = await run_local_case(case, path_name, tmp_path / "other", recorded_checksums)

    assert actual == expected


# ----------------------------------------------------------------------------------------------------------
# The same cases on S3, with the requests each path sends
# ----------------------------------------------------------------------------------------------------------
@dataclass
class S3Case:
    name: str
    stored: bytes | None
    checksums: frozenset[str] = frozenset()
    fail_on: str | None = None
    expected_outcome: str = ""
    expected_encrypted: bool = False


S3_CASES = [
    S3Case("verified", CONTENT, frozenset({CONTENT_MD5}), expected_outcome="encrypted", expected_encrypted=True),
    S3Case("checksum_mismatch", CONTENT, frozenset({OTHER_MD5}), expected_outcome="skipped_checksum_mismatch"),
    S3Case("orphan", CONTENT, expected_outcome="skipped_unverified"),
    S3Case("over_the_limit", OVER_LIMIT, frozenset({OTHER_MD5}), expected_outcome="skipped_too_large"),
    S3Case("already_encrypted", SEALED, frozenset({CONTENT_MD5}), expected_outcome="already_encrypted"),
    S3Case("sealed_with_another_key", SEALED_OTHER_KEY, frozenset({CONTENT_MD5}), expected_outcome="failed"),
    S3Case("truncated_envelope", SEALED[:25], frozenset({CONTENT_MD5}), expected_outcome="failed"),
    S3Case("missing_object", None, frozenset({CONTENT_MD5}), expected_outcome="missing"),
    S3Case("empty_object_without_checksum", b"", expected_outcome="skipped_unverified"),
    S3Case(
        "empty_object_with_its_checksum",
        b"",
        frozenset({EMPTY_MD5}),
        expected_outcome="encrypted",
        expected_encrypted=True,
    ),
    S3Case("write_refused", CONTENT, frozenset({CONTENT_MD5}), fail_on="put", expected_outcome="failed"),
]


async def run_s3_case(
    case: S3Case, path_name: str, root: Path, table: dict[str, frozenset[str]]
) -> tuple[Described, dict[str, Any], FakeS3Bucket]:
    make_root(root, None)
    bucket = FakeS3Bucket()
    if case.stored is not None:
        bucket.objects[IDENTIFIER] = case.stored
    bucket.fail_on = case.fail_on
    storage = build_s3_storage(root, bucket)
    originals = dict(bucket.objects)
    table[IDENTIFIER] = case.checksums
    registry._storage = storage
    try:
        described = await PATHS[path_name](Call(storage=storage, identifier=IDENTIFIER))
    except (HTTPException, StorageEncryptionError) as error:
        described = describe_error(error)
    bucket.fail_on = None
    return described, snapshot(storage, dict(bucket.objects), originals), bucket


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in S3_CASES])
async def test_shared_function_on_s3_gives_the_expected_outcome(
    case: S3Case, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    described, state, _ = await run_s3_case(case, REFERENCE, tmp_path, recorded_checksums)

    assert described[:2] == ("result", case.expected_outcome)
    assert [value != "unchanged" for value in state.values()] == (
        [case.expected_encrypted] if case.stored is not None else []
    )


@pytest.mark.parametrize("path_name", [name for name in PATHS if name != REFERENCE])
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in S3_CASES])
async def test_every_path_gives_the_same_outcome_and_objects_on_s3(
    case: S3Case, path_name: str, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    expected = await run_s3_case(case, REFERENCE, tmp_path / "ref", recorded_checksums)

    actual = await run_s3_case(case, path_name, tmp_path / "other", recorded_checksums)

    assert actual[:2] == expected[:2]


@dataclass
class S3ErrorCase:
    name: str
    fail_on: str
    expected_outcome: str
    expected_encrypted: bool


S3_ERROR_CASES = [
    S3ErrorCase(name="full_read_refused", fail_on="read", expected_outcome="failed", expected_encrypted=False),
    # The size comes with the answer of the read, so a refused size request does not stop the encryption.
    S3ErrorCase(name="size_request_refused", fail_on="size", expected_outcome="encrypted", expected_encrypted=True),
]


@pytest.mark.parametrize("path_name", list(PATHS))
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in S3_ERROR_CASES])
async def test_s3_errors_give_the_same_outcome_on_every_path(
    case: S3ErrorCase, path_name: str, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    s3_case = S3Case(case.name, CONTENT, frozenset({CONTENT_MD5}), fail_on=case.fail_on)

    described, state, _ = await run_s3_case(s3_case, path_name, tmp_path, recorded_checksums)

    assert described[1] == case.expected_outcome
    assert [value != "unchanged" for value in state.values()] == [case.expected_encrypted]


# ----------------------------------------------------------------------------------------------------------
# Peek and request counts
# ----------------------------------------------------------------------------------------------------------
PEEK_STORED = [
    pytest.param(CONTENT, id="plain"),
    pytest.param(SEALED, id="encrypted"),
    pytest.param(SEALED_OTHER_KEY, id="other_key"),
    pytest.param(SEALED[:25], id="truncated"),
    pytest.param(b"", id="empty"),
    pytest.param(b"x" * 5000, id="larger_than_the_peek"),
]


@pytest.mark.parametrize("stored", PEEK_STORED)
async def test_peek_changes_the_bytes_asked_for_and_never_the_header_that_is_judged(
    stored: bytes, tmp_path: Path
) -> None:
    results = {}
    for request_length in (HEADER_PEEK_LENGTH, HEADER_REQUEST_LENGTH):
        bucket = FakeS3Bucket()
        bucket.objects[IDENTIFIER] = stored
        storage = build_s3_storage(tmp_path, bucket)
        results[request_length] = (
            storage.read_header(identifier=IDENTIFIER, request_length=request_length),
            storage.inspect_encryption(identifier=IDENTIFIER, request_length=request_length),
        )
        asked = [length for kind, length in bucket.calls if kind == "head"]
        assert asked == [request_length] * 2

    assert results[HEADER_PEEK_LENGTH] == results[HEADER_REQUEST_LENGTH]
    assert len(results[HEADER_REQUEST_LENGTH][0] or b"") <= HEADER_PEEK_LENGTH


async def test_an_object_is_encrypted_with_four_requests_to_s3(
    tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    recorded_checksums[IDENTIFIER] = frozenset({CONTENT_MD5})
    bucket = FakeS3Bucket()
    bucket.objects[IDENTIFIER] = CONTENT
    storage = build_s3_storage(tmp_path, bucket)
    registry._storage = storage

    await PATHS[REFERENCE](Call(storage=storage, identifier=IDENTIFIER))

    assert [kind for kind, _ in bucket.calls] == ["head", "get", "put", "head"]


# ----------------------------------------------------------------------------------------------------------
# Refusals before any object is touched
# ----------------------------------------------------------------------------------------------------------
@dataclass
class ReadinessCase:
    name: str
    stored: bytes | None
    key: StorageKey | None
    encryption_enabled: bool


READINESS_CASES = [
    ReadinessCase("no_key_plain_object", CONTENT, None, True),
    ReadinessCase("no_key_encrypted_object", SEALED, None, True),
    ReadinessCase("no_key_missing_object", None, None, True),
    ReadinessCase("encryption_disabled_plain_object", CONTENT, KEY, False),
    ReadinessCase("encryption_disabled_encrypted_object", SEALED, KEY, False),
    ReadinessCase("encryption_disabled_missing_object", None, KEY, False),
]


async def run_readiness(
    case: ReadinessCase, path_name: str, root: Path, table: dict[str, frozenset[str]]
) -> tuple[Described, dict[str, Any]]:
    make_root(root, case.stored)
    storage = build_local_storage(root, key=case.key, encryption_enabled=case.encryption_enabled)
    originals = read_files(root)
    table[IDENTIFIER] = frozenset({CONTENT_MD5})
    registry._storage = storage
    try:
        described = await PATHS[path_name](Call(storage=storage, identifier=IDENTIFIER))
    except (HTTPException, StorageEncryptionError) as error:
        described = describe_error(error)
    return described, snapshot(storage, read_files(root), originals)


@pytest.mark.parametrize("path_name", list(PATHS))
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in READINESS_CASES])
async def test_every_path_refuses_when_encryption_is_not_ready_whatever_the_object(
    case: ReadinessCase, path_name: str, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    described, state = await run_readiness(case, path_name, tmp_path, recorded_checksums)

    assert described[:2] == ("error", 409)
    assert all(value == "unchanged" for value in state.values())


@pytest.mark.parametrize("allow_unverified", [False, True])
async def test_batch_with_several_files_gives_each_the_outcome_of_the_shared_function(
    allow_unverified: bool, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    """All the cases of the local storage in one request, against one run of the shared function per case."""
    cases = [
        case
        for case in CASES
        if case.storage_cls is InfrahubObjectStorage and case.allow_unverified is allow_unverified and case.stored
    ]
    expected = {}
    for case in cases:
        described, state = await run_local_case(case, REFERENCE, tmp_path / f"ref-{case.name}", recorded_checksums)
        expected[case.name] = (described, state[IDENTIFIER])
    batch_path = tmp_path / "batch"
    batch_path.mkdir()
    identifiers = {case.name: f"{index:04d}-{case.name}" for index, case in enumerate(cases)}
    for case in cases:
        (batch_path / identifiers[case.name]).write_bytes(case.stored or b"")
        recorded_checksums[identifiers[case.name]] = case.checksums
    storage = build_local_storage(batch_path)
    registry._storage = storage
    originals = {entry.name: entry.read_bytes() for entry in batch_path.iterdir()}

    response = await encrypt_stored_objects_route(
        request=EncryptBatchRequest(
            identifiers=list(identifiers.values()),
            allow_unverified=allow_unverified,
        ),
        db=NO_DATABASE,
        permission_manager=ALLOW_ALL,
        http_request=CALLER_REQUEST,
        account=CALLER_ACCOUNT,
    )

    by_identifier = {result.identifier: result for result in response.results}
    state = snapshot(storage, {entry.name: entry.read_bytes() for entry in batch_path.iterdir()}, originals)
    for case in cases:
        result = by_identifier[identifiers[case.name]]
        reference_result, reference_state = expected[case.name]
        actual_result = describe_result(result.identifier, result.outcome, result.size, result.reason)
        assert (case.name, actual_result, state[identifiers[case.name]]) == (
            case.name,
            reference_result,
            reference_state,
        )


async def test_object_sealed_with_another_key_during_the_call_is_reported_as_unreadable(
    tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    case = next(case for case in CASES if case.name == "object_sealed_with_another_key_during_the_call")

    described, _ = await run_local_case(case, REFERENCE, tmp_path, recorded_checksums)

    assert described == (
        "result",
        "failed",
        0,
        "the object starts like an encrypted one but is unreadable: unknown_key",
    )


@pytest.mark.parametrize("path_name", list(PATHS))
async def test_each_header_read_of_every_path_asks_for_the_same_number_of_bytes(
    path_name: str, tmp_path: Path, recorded_checksums: dict[str, frozenset[str]]
) -> None:
    case = S3Case("verified", CONTENT, frozenset({CONTENT_MD5}))

    described, _, bucket = await run_s3_case(case, path_name, tmp_path / "root", recorded_checksums)

    assert described[:2] == ("result", "encrypted")
    assert {length for kind, length in bucket.calls if kind == "head"} == {HEADER_REQUEST_LENGTH}
