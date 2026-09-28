from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.config import FileSystemStorageSettings, StorageSettings
from infrahub.exceptions import NodeNotFoundError, StorageEncryptionError, StorageIntegrityError
from infrahub.storage import InfrahubObjectStorage, StoredContent
from infrahub.storage_encryption.crypto import StorageKey, seal

if TYPE_CHECKING:
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
    envelope = seal(identifier=OTHER_IDENTIFIER, content=CONTENT, key=KEY)
    (tmp_path / OTHER_IDENTIFIER).write_bytes(envelope)

    storage.store(identifier=IDENTIFIER, content=io.BytesIO(CONTENT))

    assert (tmp_path / IDENTIFIER).read_bytes() == CONTENT
    assert storage.read(identifier=IDENTIFIER) == StoredContent(content=CONTENT, authenticated=False)
    assert storage.read(identifier=OTHER_IDENTIFIER) == StoredContent(content=envelope, authenticated=False)


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
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSED_READ_CASES])
def test_encrypted_storage_refuses_an_envelope_that_does_not_authenticate(
    tmp_path: Path, case: RefusedReadCase
) -> None:
    storage = build_storage(tmp_path, encryption_enabled=True, key=KEY)
    (tmp_path / IDENTIFIER).write_bytes(case.stored)

    with pytest.raises(StorageIntegrityError) as excinfo:
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
