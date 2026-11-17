from __future__ import annotations

import asyncio
import io
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self

import botocore.exceptions
import pytest

from infrahub.config import FileSystemStorageSettings, StorageSettings
from infrahub.core.constants import ArtifactEncryption
from infrahub.exceptions import NodeNotFoundError, StorageEncryptionError, StorageIntegrityError
from infrahub.storage import (
    InfrahubObjectStorage,
    InfrahubS3ObjectStorage,
    StoredContent,
    StoredObject,
    StoredObjectListing,
)
from infrahub.storage_encryption.crypto import StorageKey, seal
from infrahub.storage_encryption.status import HEADER_PEEK_LENGTH, EncryptionCheck, UnreadableReason
from tests.helpers.storage import vanishing_directory

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

KEY = StorageKey.derive("unit-test-secret-key-0123456789abcdef")
OTHER_KEY = StorageKey.derive("another-unit-test-secret-key-987654321")
IDENTIFIER = "18a3f2e4-5c3d-4b1e-a0f7-3c9d2b6e8f01"
OTHER_IDENTIFIER = "c0ffee00-5c3d-4b1e-a0f7-3c9d2b6e8f01"
CONTENT = b"hostname leaf01\ninterface Ethernet1\n  description uplink to spine01\n"


def build_storage(path: Path, *, encryption_enabled: bool, key: StorageKey | None) -> InfrahubObjectStorage:
    return InfrahubObjectStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": path}), encryption_enabled=encryption_enabled
        ),
        key=key,
    )


def test_encrypted_storage_writes_ciphertext_and_reads_it_back_authenticated(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    storage.store(identifier=IDENTIFIER, content=io.BytesIO(CONTENT))

    stored = (tmp_path / IDENTIFIER).read_bytes()
    assert stored[:13] == b"IHSE\x01" + bytes.fromhex(KEY.fingerprint)
    assert b"leaf01" not in stored
    assert storage.read(identifier=IDENTIFIER) == StoredContent(content=CONTENT, authenticated=True)
    assert storage.retrieve(identifier=IDENTIFIER) == CONTENT.decode()


def test_encrypted_storage_encrypts_the_whole_stream_whatever_its_position(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    upload = io.BytesIO(CONTENT)
    upload.read()

    storage.store(identifier=IDENTIFIER, content=upload)

    assert storage.retrieve_binary(identifier=IDENTIFIER) == CONTENT


def test_file_stored_before_encryption_is_returned_unauthenticated(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert storage.read(identifier=IDENTIFIER) == StoredContent(content=CONTENT, authenticated=False)


def test_plaintext_storage_is_unchanged_by_the_encryption_support(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=False, key=None)

    storage.store(identifier=IDENTIFIER, content=io.BytesIO(CONTENT))

    assert (tmp_path / IDENTIFIER).read_bytes() == CONTENT
    assert storage.read(identifier=IDENTIFIER) == StoredContent(content=CONTENT, authenticated=False)


def test_disabled_storage_still_reads_what_was_encrypted(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(seal(identifier=IDENTIFIER, content=CONTENT, key=KEY))
    storage = build_storage(tmp_path, encryption_enabled=False, key=KEY)

    assert storage.read(identifier=IDENTIFIER) == StoredContent(content=CONTENT, authenticated=True)
    assert storage.retrieve_binary(identifier=IDENTIFIER) == CONTENT


def test_disabled_storage_writes_plaintext_even_with_a_key(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=False, key=KEY)

    storage.store(identifier=IDENTIFIER, content=io.BytesIO(CONTENT))

    assert (tmp_path / IDENTIFIER).read_bytes() == CONTENT


def test_disabled_storage_refuses_an_encrypted_object_it_has_no_key_for(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=False, key=None)
    (tmp_path / IDENTIFIER).write_bytes(seal(identifier=IDENTIFIER, content=CONTENT, key=KEY))

    with pytest.raises(
        StorageEncryptionError,
        match=(
            rf"^The stored object {IDENTIFIER} is encrypted but this process has no key to decrypt it; set "
            r"INFRAHUB_STORAGE_ENCRYPTION_KEY, or INFRAHUB_SECURITY_SECRET_KEY when no dedicated key was used, to the "
            r"value that was in use when encryption was enabled$"
        ),
    ):
        storage.read(identifier=IDENTIFIER)


def test_disabled_storage_refuses_an_object_encrypted_with_another_key(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=False, key=OTHER_KEY)
    (tmp_path / IDENTIFIER).write_bytes(seal(identifier=IDENTIFIER, content=CONTENT, key=KEY))

    with pytest.raises(
        StorageIntegrityError,
        match=rf"^The stored content {IDENTIFIER} failed its integrity check and was not served\.$",
    ) as excinfo:
        storage.read(identifier=IDENTIFIER)

    assert excinfo.value.reason == "unknown_key"


def test_disabled_storage_does_not_refuse_plain_text_that_starts_like_the_marker(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=False, key=KEY)
    (tmp_path / IDENTIFIER).write_bytes(b"IHSE plain text that merely starts like the marker")

    assert storage.read(identifier=IDENTIFIER) == StoredContent(
        content=b"IHSE plain text that merely starts like the marker", authenticated=False
    )


@dataclass
class RefusedReadCase:
    name: str
    stored: bytes
    reason: str


REFUSED_READ_CASES = [
    RefusedReadCase(
        name="encrypted_with_another_key",
        stored=seal(identifier=IDENTIFIER, content=CONTENT, key=OTHER_KEY),
        reason="unknown_key",
    ),
    RefusedReadCase(
        name="copied_from_another_object",
        stored=seal(identifier=OTHER_IDENTIFIER, content=CONTENT, key=KEY),
        reason="tampered",
    ),
    RefusedReadCase(
        name="truncated_to_its_header",
        stored=seal(identifier=IDENTIFIER, content=CONTENT, key=KEY)[:25],
        reason="tampered",
    ),
    RefusedReadCase(name="truncated_to_its_magic", stored=b"IHSE", reason="unsupported_format"),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSED_READ_CASES])
def test_encrypted_storage_refuses_an_envelope_that_does_not_authenticate(
    tmp_path: Path, case: RefusedReadCase
) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    (tmp_path / IDENTIFIER).write_bytes(case.stored)

    with pytest.raises(
        StorageIntegrityError,
        match=rf"^The stored content {IDENTIFIER} failed its integrity check and was not served\.$",
    ) as excinfo:
        storage.read(identifier=IDENTIFIER)

    assert (excinfo.value.identifier, excinfo.value.reason) == (IDENTIFIER, case.reason)


def test_encrypted_storage_reports_a_missing_object_as_missing(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    with pytest.raises(
        NodeNotFoundError, match=rf"Unable to find the node {IDENTIFIER} / StorageObject in the database\."
    ):
        storage.read(identifier=IDENTIFIER)


def test_encrypted_storage_without_a_key_refuses_to_write_or_open_an_envelope(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=None)
    (tmp_path / IDENTIFIER).write_bytes(seal(identifier=IDENTIFIER, content=CONTENT, key=KEY))
    message = (
        r"^Storage encryption is enabled but this process has no key; only the API server reads and writes "
        r"stored objects$"
    )

    with pytest.raises(StorageEncryptionError, match=message):
        storage.store(identifier=OTHER_IDENTIFIER, content=io.BytesIO(CONTENT))
    with pytest.raises(StorageEncryptionError, match=message):
        storage.read(identifier=IDENTIFIER)
    assert sorted(entry.name for entry in tmp_path.iterdir()) == [IDENTIFIER]


def test_header_of_a_stored_object_is_its_first_bytes(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    storage.store(identifier=IDENTIFIER, content=io.BytesIO(CONTENT))

    header = storage.read_header(identifier=IDENTIFIER)

    assert header == (tmp_path / IDENTIFIER).read_bytes()[:HEADER_PEEK_LENGTH]


def test_header_of_a_missing_object_is_none(tmp_path: Path) -> None:
    assert build_storage(tmp_path, encryption_enabled=True, key=KEY).read_header(identifier=IDENTIFIER) is None


def test_inspection_follows_the_key_of_the_storage(tmp_path: Path) -> None:
    sealed_with_key = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    sealed_with_key.store(identifier=IDENTIFIER, content=io.BytesIO(CONTENT))

    with_key = sealed_with_key.inspect_encryption(identifier=IDENTIFIER)
    other_key = build_storage(tmp_path, encryption_enabled=True, key=OTHER_KEY).inspect_encryption(
        identifier=IDENTIFIER
    )

    assert (with_key, other_key) == (
        EncryptionCheck(encryption=ArtifactEncryption.ENCRYPTED, reason=None),
        EncryptionCheck(encryption=ArtifactEncryption.UNREADABLE, reason=UnreadableReason.UNKNOWN_KEY),
    )


def client_error(code: str) -> botocore.exceptions.ClientError:
    return botocore.exceptions.ClientError(error_response={"Error": {"Code": code}}, operation_name="GetObject")


class FailingObject:
    def __init__(self, error: botocore.exceptions.ClientError) -> None:
        self.error = error

    def get(self, Range: str) -> dict:  # noqa: N803
        raise self.error


class FailingBucket:
    def __init__(self, error: botocore.exceptions.ClientError) -> None:
        self.error = error

    def Object(self, name: str) -> FailingObject:  # noqa: N802
        return FailingObject(self.error)


class FailingS3Storage(InfrahubS3ObjectStorage):
    """An S3 object storage whose reads fail with a given client error."""

    def __init__(self, error: botocore.exceptions.ClientError) -> None:
        self._bucket = FailingBucket(error)  # type: ignore[assignment]


def build_s3_storage_failing_with(path: Path, code: str) -> InfrahubObjectStorage:
    storage = build_storage(path, encryption_enabled=True, key=KEY)
    storage._storage = FailingS3Storage(error=client_error(code))
    return storage


@pytest.mark.parametrize("code", ["NoSuchKey", "404", "NotFound"])
def test_header_of_an_s3_object_that_does_not_exist_is_none(tmp_path: Path, code: str) -> None:
    storage = build_s3_storage_failing_with(tmp_path, code)

    assert storage.read_header(identifier=IDENTIFIER) is None


@pytest.mark.parametrize("code", ["AccessDenied", "NoSuchBucket", "SlowDown"])
def test_header_of_an_s3_object_is_not_read_when_the_storage_fails(tmp_path: Path, code: str) -> None:
    storage = build_s3_storage_failing_with(tmp_path, code)

    with pytest.raises(botocore.exceptions.ClientError, match=rf"\({code}\) when calling the GetObject"):
        storage.read_header(identifier=IDENTIFIER)


def test_header_of_an_empty_s3_object_is_empty(tmp_path: Path) -> None:
    storage = build_s3_storage_failing_with(tmp_path, "InvalidRange")

    assert storage.read_header(identifier=IDENTIFIER) == b""


LISTED_IDENTIFIERS = [
    "18a3f2e4-0000-4b1e-a0f7-3c9d2b6e8f01",
    "18a3f2e4-1111-4b1e-a0f7-3c9d2b6e8f01",
    "18a3f2e4-2222-4b1e-a0f7-3c9d2b6e8f01",
    "18a3f2e4-3333-4b1e-a0f7-3c9d2b6e8f01",
    "18a3f2e4-4444-4b1e-a0f7-3c9d2b6e8f01",
]


def write_listed_objects(path: Path) -> None:
    """Create the listed objects in an order that is not the sorted one, each with its own size and time."""
    for position in (3, 0, 4, 2, 1):
        target = path / LISTED_IDENTIFIERS[position]
        target.write_bytes(b"x" * (position + 1))
        os.utime(target, (1_700_000_000 + position, 1_700_000_000 + position))


def test_listing_yields_every_object_in_identifier_order_with_its_size_and_time(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert list(storage.list_objects()) == [
        StoredObject(
            identifier=identifier,
            size=position + 1,
            last_modified=datetime.fromtimestamp(1_700_000_000 + position, tz=UTC),
        )
        for position, identifier in enumerate(LISTED_IDENTIFIERS)
    ]


def test_listing_pages_through_the_storage_with_start_after_and_limit(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    pages = []
    start_after = None
    while page := [stored.identifier for stored in storage.list_objects(start_after=start_after, limit=2)]:
        pages.append(page)
        start_after = page[-1]

    assert pages == [LISTED_IDENTIFIERS[0:2], LISTED_IDENTIFIERS[2:4], LISTED_IDENTIFIERS[4:5]]


def test_listing_starts_strictly_after_an_identifier_that_is_not_stored(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    listed = [stored.identifier for stored in storage.list_objects(start_after="18a3f2e4-2")]

    assert listed == LISTED_IDENTIFIERS[2:]


def test_listing_with_a_limit_of_zero_yields_nothing(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert list(storage.list_objects(limit=0)) == []


def test_listing_refuses_a_negative_limit(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    with pytest.raises(ValueError, match=r"^limit must not be negative$"):
        list(storage.list_objects(limit=-1))


def test_listing_skips_unfinished_writes_and_directories(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    (tmp_path / f".{IDENTIFIER}.0123456789abcdef.tmp").write_bytes(b"half written")
    (tmp_path / "a-directory").mkdir()
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert [stored.identifier for stored in storage.list_objects()] == [IDENTIFIER]
    assert [stored.identifier for stored in storage.list_objects(limit=10)] == [IDENTIFIER]


def list_pages(storage: InfrahubObjectStorage, limit: int) -> list[StoredObjectListing]:
    pages: list[StoredObjectListing] = []
    start_after = None
    while True:
        page = storage.list_page(start_after=start_after, limit=limit)
        pages.append(page)
        if page.next_start_after is None:
            return pages
        start_after = page.next_start_after


def identifiers_of(page: StoredObjectListing) -> list[str]:
    return [stored.identifier for stored in page.objects]


def test_page_after_an_object_that_vanished_between_the_scan_and_the_read_still_has_a_next_page(
    tmp_path: Path,
) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    storage._storage._path = vanishing_directory(tmp_path, frozenset({LISTED_IDENTIFIERS[1]}))  # type: ignore[union-attr]

    pages = list_pages(storage, limit=3)

    assert [(identifiers_of(page), page.next_start_after) for page in pages] == [
        ([LISTED_IDENTIFIERS[0], LISTED_IDENTIFIERS[2]], LISTED_IDENTIFIERS[2]),
        (LISTED_IDENTIFIERS[3:], None),
    ]


def test_page_whose_objects_all_vanished_is_empty_and_points_to_the_next_page(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    storage._storage._path = vanishing_directory(tmp_path, frozenset(LISTED_IDENTIFIERS[:2]))  # type: ignore[union-attr]

    first = storage.list_page(start_after=None, limit=2)

    assert first == StoredObjectListing(objects=[], next_start_after=LISTED_IDENTIFIERS[1])


def test_listing_pages_cover_every_object_once_whatever_the_limit(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    covered = {
        limit: [i for page in list_pages(storage, limit) for i in identifiers_of(page)] for limit in (1, 2, 3, 5, 6)
    }

    assert covered == dict.fromkeys((1, 2, 3, 5, 6), LISTED_IDENTIFIERS)


def test_last_page_that_ends_exactly_at_the_limit_has_no_next_page(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    pages = list_pages(storage, limit=5)

    assert [(identifiers_of(page), page.next_start_after) for page in pages] == [(LISTED_IDENTIFIERS, None)]


def test_page_that_ends_before_the_last_object_points_to_the_last_identifier_it_holds(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    page = storage.list_page(start_after=None, limit=4)

    assert (identifiers_of(page), page.next_start_after) == (LISTED_IDENTIFIERS[:4], LISTED_IDENTIFIERS[3])


def test_page_of_an_empty_directory_has_no_object_and_no_next_page(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert storage.list_page(start_after=None, limit=3) == StoredObjectListing(objects=[], next_start_after=None)


def test_page_after_the_last_name_has_no_object_and_no_next_page(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert storage.list_page(start_after="zzzz", limit=3) == StoredObjectListing(objects=[], next_start_after=None)
    assert storage.list_page(start_after=LISTED_IDENTIFIERS[4], limit=3) == StoredObjectListing(
        objects=[], next_start_after=None
    )


def test_page_starts_strictly_after_a_cursor_that_sorts_between_two_names(tmp_path: Path) -> None:
    write_listed_objects(tmp_path)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    between = storage.list_page(start_after="18a3f2e4-1111-4b1e-a0f7-3c9d2b6e8f00", limit=2)
    equal = storage.list_page(start_after=LISTED_IDENTIFIERS[1], limit=2)
    before_all = storage.list_page(start_after="0", limit=1)

    assert [(identifiers_of(page), page.next_start_after) for page in (between, equal, before_all)] == [
        (LISTED_IDENTIFIERS[1:3], LISTED_IDENTIFIERS[2]),
        (LISTED_IDENTIFIERS[2:4], LISTED_IDENTIFIERS[3]),
        (LISTED_IDENTIFIERS[:1], LISTED_IDENTIFIERS[0]),
    ]


def test_page_ignores_unfinished_writes_when_it_decides_whether_a_next_page_exists(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    (tmp_path / f".{IDENTIFIER}.0123456789abcdef.tmp").write_bytes(b"half written")
    (tmp_path / "z-directory").mkdir()
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    page = storage.list_page(start_after=None, limit=1)

    assert (identifiers_of(page), page.next_start_after) == ([IDENTIFIER], None)


def test_page_refuses_a_limit_below_one(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    with pytest.raises(ValueError, match=r"^limit must be at least 1$"):
        storage.list_page(start_after=None, limit=0)


class ListedKeys:
    """What a bucket returns for a listing: keys after a marker, cut at a limit, like a boto3 collection."""

    def __init__(self, keys: list[str], marker: str | None = None, cut: int | None = None) -> None:
        self.keys, self.marker, self.cut = keys, marker, cut

    def filter(self, Marker: str) -> Self:  # noqa: N803
        return type(self)(self.keys, marker=Marker, cut=self.cut)

    def all(self) -> Self:
        return self

    def limit(self, count: int) -> Self:
        return type(self)(self.keys, marker=self.marker, cut=count)

    def __iter__(self) -> Iterator[object]:
        after = [key for key in sorted(self.keys) if self.marker is None or key > self.marker]
        for key in after[: self.cut]:
            yield type("Summary", (), {"key": key, "size": 1, "last_modified": datetime(2024, 5, 17, tzinfo=UTC)})()


class ListingBucket:
    def __init__(self, keys: list[str]) -> None:
        self.objects = ListedKeys(keys)


class ListingS3Storage(InfrahubS3ObjectStorage):
    def __init__(self, keys: list[str]) -> None:
        self._bucket = ListingBucket(keys)  # type: ignore[assignment]


def test_s3_pages_cover_every_key_once_and_the_last_page_ends_exactly_at_the_limit(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    storage._storage = ListingS3Storage(keys=LISTED_IDENTIFIERS)

    two = list_pages(storage, limit=2)
    exact = list_pages(storage, limit=5)

    assert ([(identifiers_of(page), page.next_start_after) for page in two]) == [
        (LISTED_IDENTIFIERS[0:2], LISTED_IDENTIFIERS[1]),
        (LISTED_IDENTIFIERS[2:4], LISTED_IDENTIFIERS[3]),
        (LISTED_IDENTIFIERS[4:5], None),
    ]
    assert [(identifiers_of(page), page.next_start_after) for page in exact] == [(LISTED_IDENTIFIERS, None)]


def test_s3_page_after_the_last_key_has_no_object_and_no_next_page(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    storage._storage = ListingS3Storage(keys=LISTED_IDENTIFIERS)

    assert storage.list_page(start_after=LISTED_IDENTIFIERS[4], limit=3) == StoredObjectListing(
        objects=[], next_start_after=None
    )


def test_size_of_a_stored_object_is_read_without_its_content(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert (storage.get_size(identifier=IDENTIFIER), storage.get_size(identifier=OTHER_IDENTIFIER)) == (68, None)


def test_replace_overwrites_the_object_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    storage.replace(identifier=IDENTIFIER, content=b"replaced")

    assert {entry.name: entry.read_bytes() for entry in tmp_path.iterdir()} == {IDENTIFIER: b"replaced"}


def test_replace_writes_the_content_as_given_even_with_encryption_enabled(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    storage.replace(identifier=IDENTIFIER, content=b"not sealed by replace")

    assert (tmp_path / IDENTIFIER).read_bytes() == b"not sealed by replace"


def test_replace_swaps_the_file_instead_of_writing_into_it(tmp_path: Path) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    with (tmp_path / IDENTIFIER).open("rb") as reader_of_the_previous_object:
        storage.replace(identifier=IDENTIFIER, content=b"replaced")
        seen_by_the_reader = reader_of_the_previous_object.read()

    assert (seen_by_the_reader, (tmp_path / IDENTIFIER).read_bytes()) == (CONTENT, b"replaced")


def test_replace_refuses_an_identifier_that_has_no_object(tmp_path: Path) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    with pytest.raises(
        NodeNotFoundError, match=rf"Unable to find the node {IDENTIFIER} / StorageObject in the database\."
    ):
        storage.replace(identifier=IDENTIFIER, content=b"replaced")

    assert list(tmp_path.iterdir()) == []


@dataclass
class ReplaceFailureCase:
    name: str
    failure: BaseException
    message: str


REPLACE_FAILURE_CASES = [
    ReplaceFailureCase(
        name="disk_full",
        failure=OSError(28, "No space left on device"),
        message=r"^\[Errno 28\] No space left on device$",
    ),
    ReplaceFailureCase(name="cancelled", failure=asyncio.CancelledError(), message=r"^$"),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REPLACE_FAILURE_CASES])
def test_replace_that_fails_leaves_the_object_and_no_temporary_file(
    case: ReplaceFailureCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / IDENTIFIER).write_bytes(CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    def fail(fd: int) -> None:
        raise case.failure

    monkeypatch.setattr(os, "fsync", fail)

    with pytest.raises(type(case.failure), match=case.message):
        storage.replace(identifier=IDENTIFIER, content=b"replaced")

    monkeypatch.undo()
    assert {entry.name: entry.read_bytes() for entry in tmp_path.iterdir()} == {IDENTIFIER: CONTENT}


TEMPORARY_NAME = f".{IDENTIFIER}.0123456789abcdef.tmp"
HOURS = 3600


def write_aged(path: Path, name: str, age_seconds: float, content: bytes = b"x") -> None:
    target = path / name
    target.write_bytes(content)
    aged = time.time() - age_seconds
    os.utime(target, (aged, aged))


def test_stale_temporary_files_are_removed_and_nothing_else(tmp_path: Path) -> None:
    other_temporary = f".{OTHER_IDENTIFIER}.fedcba9876543210.tmp"
    write_aged(tmp_path, TEMPORARY_NAME, 2 * HOURS, b"half written")
    write_aged(tmp_path, other_temporary, 3 * HOURS, b"half written")
    write_aged(tmp_path, IDENTIFIER, 5 * HOURS, CONTENT)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    removed = storage.remove_stale_temporary_files()

    assert (removed, sorted(entry.name for entry in tmp_path.iterdir())) == (
        sorted([TEMPORARY_NAME, other_temporary]),
        [IDENTIFIER],
    )


def test_temporary_file_of_a_write_that_may_be_in_progress_is_kept(tmp_path: Path) -> None:
    write_aged(tmp_path, TEMPORARY_NAME, 10 * 60, b"being written")
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert (storage.remove_stale_temporary_files(), (tmp_path / TEMPORARY_NAME).read_bytes()) == ([], b"being written")


@dataclass
class KeptNameCase:
    name: str
    file_name: str


KEPT_NAME_CASES = [
    KeptNameCase(name="object_named_like_an_identifier", file_name=IDENTIFIER),
    KeptNameCase(name="hidden_file_with_the_suffix_only", file_name=".something.tmp"),
    KeptNameCase(name="token_too_short", file_name=f".{IDENTIFIER}.0123456789abcde.tmp"),
    KeptNameCase(name="token_not_hexadecimal", file_name=f".{IDENTIFIER}.0123456789abcdeg.tmp"),
    KeptNameCase(name="no_leading_dot", file_name=f"{IDENTIFIER}.0123456789abcdef.tmp"),
    KeptNameCase(name="other_suffix", file_name=f".{IDENTIFIER}.0123456789abcdef.part"),
    KeptNameCase(name="trailing_newline", file_name=f".{IDENTIFIER}.0123456789abcdef.tmp\n"),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in KEPT_NAME_CASES])
def test_old_file_whose_name_is_not_exactly_that_of_a_temporary_file_is_kept(
    case: KeptNameCase, tmp_path: Path
) -> None:
    write_aged(tmp_path, case.file_name, 10 * HOURS)
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)

    assert (storage.remove_stale_temporary_files(), [entry.name for entry in tmp_path.iterdir()]) == (
        [],
        [case.file_name],
    )


def test_old_directory_and_symbolic_link_with_a_temporary_name_are_kept(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "target"
    target.write_bytes(b"not ours")
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    directory_name = f".{IDENTIFIER}.0123456789abcdef.tmp"
    link_name = f".{OTHER_IDENTIFIER}.0123456789abcdef.tmp"
    (storage_dir / directory_name).mkdir()
    (storage_dir / link_name).symlink_to(target)
    aged = time.time() - 10 * HOURS
    os.utime(target, (aged, aged))
    os.utime(storage_dir / link_name, (aged, aged), follow_symlinks=False)
    storage = build_storage(storage_dir, encryption_enabled=True, key=KEY)

    removed = storage.remove_stale_temporary_files()

    assert (removed, sorted(entry.name for entry in storage_dir.iterdir()), target.read_bytes()) == (
        [],
        sorted([directory_name, link_name]),
        b"not ours",
    )


def test_removing_stale_temporary_files_of_an_s3_storage_does_nothing(tmp_path: Path) -> None:
    storage = build_s3_storage_failing_with(tmp_path, "AccessDenied")

    assert storage.remove_stale_temporary_files() == []
