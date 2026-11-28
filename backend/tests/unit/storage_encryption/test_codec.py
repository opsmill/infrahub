from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, BinaryIO

import pytest
from structlog.testing import capture_logs

from infrahub.config import FileSystemStorageSettings, SecuritySettings, StorageSettings
from infrahub.exceptions import StorageEncryptionError, StorageIntegrityError
from infrahub.storage import InfrahubObjectStorage
from infrahub.storage_encryption.codec import (
    AesGcmCodec,
    DecryptOnlyCodec,
    NoKeyCodec,
    PlainCodec,
    StoredContent,
    StoredContentCodec,
    build_storage_codec,
    select_codec,
)
from infrahub.storage_encryption.crypto import IntegrityFailure, StorageKey, seal

if TYPE_CHECKING:
    from pathlib import Path

SECRET = "unit-test-secret-key-0123456789abcdef"
DEDICATED_KEY = "dedicated-storage-key-0123456789abcdef!"
KEY = StorageKey.derive(SECRET)
OTHER_KEY = StorageKey.derive("another-unit-test-secret-key-987654321")
IDENTIFIER = "18a3f2e4-5c3d-4b1e-a0f7-3c9d2b6e8f01"
CONTENT = b"hostname leaf01\ninterface Ethernet1\n"
PUBLISHED_SECRET = "327f747f-efac-42be-9e73-999f08f86b92"


@dataclass
class SelectCase:
    name: str
    encryption_enabled: bool
    key: StorageKey | None
    expected: type[StoredContentCodec]


SELECT_CASES = [
    SelectCase(name="enabled_with_a_key", encryption_enabled=True, key=KEY, expected=AesGcmCodec),
    SelectCase(name="disabled_with_a_key", encryption_enabled=False, key=KEY, expected=DecryptOnlyCodec),
    SelectCase(name="enabled_without_a_key", encryption_enabled=True, key=None, expected=NoKeyCodec),
    SelectCase(name="disabled_without_a_key", encryption_enabled=False, key=None, expected=PlainCodec),
]


@pytest.mark.parametrize("case", SELECT_CASES, ids=lambda case: case.name)
def test_codec_follows_the_setting_and_the_key_a_process_has(case: SelectCase) -> None:
    codec = select_codec(encryption_enabled=case.encryption_enabled, key=case.key)

    assert type(codec) is case.expected


@dataclass
class BuildCase:
    name: str
    encryption_enabled: bool
    encryption_key: str | None
    secret: str
    expected: type[StoredContentCodec]


BUILD_CASES = [
    BuildCase(
        name="enabled_with_the_secret",
        encryption_enabled=True,
        encryption_key=None,
        secret=SECRET,
        expected=AesGcmCodec,
    ),
    BuildCase(
        name="enabled_with_a_dedicated_key",
        encryption_enabled=True,
        encryption_key=DEDICATED_KEY,
        secret=PUBLISHED_SECRET,
        expected=AesGcmCodec,
    ),
    BuildCase(
        name="disabled_with_a_usable_secret",
        encryption_enabled=False,
        encryption_key=None,
        secret=SECRET,
        expected=DecryptOnlyCodec,
    ),
    BuildCase(
        name="disabled_with_the_published_secret",
        encryption_enabled=False,
        encryption_key=None,
        secret=PUBLISHED_SECRET,
        expected=PlainCodec,
    ),
    BuildCase(
        name="disabled_with_a_dedicated_key_that_is_too_short",
        encryption_enabled=False,
        encryption_key="too-short",
        secret=SECRET,
        expected=PlainCodec,
    ),
]


@pytest.mark.parametrize("case", BUILD_CASES, ids=lambda case: case.name)
def test_api_server_codec_is_built_from_the_settings(case: BuildCase) -> None:
    codec = build_storage_codec(
        storage=StorageSettings(encryption_enabled=case.encryption_enabled, encryption_key=case.encryption_key),
        security=SecuritySettings(secret_key=case.secret),
    )

    assert type(codec) is case.expected


def test_api_server_codec_is_not_built_while_encryption_is_enabled_with_a_key_that_cannot_be_used() -> None:
    with pytest.raises(
        StorageEncryptionError,
        match=(
            r"^INFRAHUB_SECURITY_SECRET_KEY still has the value published in Infrahub's example deployment files; "
            r"set a unique random secret, or set INFRAHUB_STORAGE_ENCRYPTION_KEY, before using storage encryption$"
        ),
    ):
        build_storage_codec(
            storage=StorageSettings(encryption_enabled=True), security=SecuritySettings(secret_key=PUBLISHED_SECRET)
        )


def test_integrity_failure_is_logged_with_the_storage_id_the_reason_and_the_key_fingerprint() -> None:
    envelope = seal(identifier=IDENTIFIER, content=CONTENT, key=OTHER_KEY)

    with capture_logs() as logs, pytest.raises(StorageIntegrityError) as excinfo:
        AesGcmCodec(KEY).decode(identifier=IDENTIFIER, stored=envelope)

    assert excinfo.value.reason == IntegrityFailure.UNKNOWN_KEY
    assert logs == [
        {
            "event": "Refused a stored object that failed its integrity check",
            "log_level": "warning",
            "storage_id": IDENTIFIER,
            "reason": IntegrityFailure.UNKNOWN_KEY,
            "key_fingerprint": KEY.fingerprint,
        }
    ]


class RecordingCodec:
    """Writes content with a prefix and reads it back, keeping what the storage passed in."""

    def __init__(self) -> None:
        self.encoded: list[tuple[str, bytes]] = []
        self.decoded: list[tuple[str, bytes]] = []

    def encode(self, identifier: str, content: BinaryIO) -> BinaryIO:
        data = content.read()
        self.encoded.append((identifier, data))
        return io.BytesIO(b"prefix:" + data)

    def decode(self, identifier: str, stored: bytes) -> StoredContent:
        self.decoded.append((identifier, stored))
        return StoredContent(content=stored.removeprefix(b"prefix:"), authenticated=True)


def test_storage_writes_what_the_codec_encodes_and_returns_what_it_decodes(tmp_path: Path) -> None:
    codec = RecordingCodec()
    storage = InfrahubObjectStorage(
        settings=StorageSettings(
            local=FileSystemStorageSettings.model_validate({"path": tmp_path}), encryption_enabled=True
        ),
        codec=codec,
    )

    storage.store(identifier=IDENTIFIER, content=io.BytesIO(CONTENT))
    read = storage.read(identifier=IDENTIFIER)

    assert (tmp_path / IDENTIFIER).read_bytes() == b"prefix:" + CONTENT
    assert codec.encoded == [(IDENTIFIER, CONTENT)]
    assert codec.decoded == [(IDENTIFIER, b"prefix:" + CONTENT)]
    assert read == StoredContent(content=CONTENT, authenticated=True)
