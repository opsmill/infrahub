from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import ArtifactEncryption
from infrahub.storage_encryption.crypto import StorageKey, seal
from infrahub.storage_encryption.status import (
    HEADER_PEEK_LENGTH,
    EncryptionCheck,
    UnreadableReason,
    check_header,
)

KEY = StorageKey.derive("unit-test-secret-key-0123456789abcdef")
OTHER_KEY = StorageKey.derive("another-unit-test-secret-key-987654321")
IDENTIFIER = "18a3f2e4-5c3d-4b1e-a0f7-3c9d2b6e8f01"
SEALED = seal(identifier=IDENTIFIER, content=b"interface Ethernet1\n", key=KEY)
SEALED_WITH_OTHER_KEY = seal(identifier=IDENTIFIER, content=b"interface Ethernet1\n", key=OTHER_KEY)
UNSUPPORTED_VERSION = SEALED[:4] + b"\x02" + SEALED[5:]


@dataclass
class HeaderCase:
    name: str
    header: bytes | None
    key: StorageKey | None
    encryption_enabled: bool
    expected: EncryptionCheck


HEADER_CASES = [
    HeaderCase(
        name="missing_object",
        header=None,
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=None, reason=UnreadableReason.MISSING),
    ),
    HeaderCase(
        name="plain_object",
        header=b"interface Ethernet1\n",
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=ArtifactEncryption.PLAINTEXT, reason=None),
    ),
    HeaderCase(
        name="empty_object",
        header=b"",
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=ArtifactEncryption.PLAINTEXT, reason=None),
    ),
    HeaderCase(
        name="sealed_with_the_current_key",
        header=SEALED[:HEADER_PEEK_LENGTH],
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=ArtifactEncryption.ENCRYPTED, reason=None),
    ),
    HeaderCase(
        name="sealed_with_the_current_key_while_encryption_is_off",
        header=SEALED[:HEADER_PEEK_LENGTH],
        key=KEY,
        encryption_enabled=False,
        expected=EncryptionCheck(encryption=ArtifactEncryption.ENCRYPTED, reason=None),
    ),
    HeaderCase(
        name="sealed_with_another_key",
        header=SEALED_WITH_OTHER_KEY[:HEADER_PEEK_LENGTH],
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=ArtifactEncryption.UNREADABLE, reason=UnreadableReason.UNKNOWN_KEY),
    ),
    HeaderCase(
        name="sealed_and_no_key",
        header=SEALED[:HEADER_PEEK_LENGTH],
        key=None,
        encryption_enabled=False,
        expected=EncryptionCheck(encryption=ArtifactEncryption.UNREADABLE, reason=UnreadableReason.NO_KEY),
    ),
    HeaderCase(
        name="truncated_envelope",
        header=SEALED[: HEADER_PEEK_LENGTH - 1],
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=ArtifactEncryption.UNREADABLE, reason=UnreadableReason.TRUNCATED),
    ),
    HeaderCase(
        name="truncated_envelope_while_encryption_is_off_is_plain",
        header=SEALED[: HEADER_PEEK_LENGTH - 1],
        key=KEY,
        encryption_enabled=False,
        expected=EncryptionCheck(encryption=ArtifactEncryption.PLAINTEXT, reason=None),
    ),
    HeaderCase(
        name="unsupported_format_version",
        header=UNSUPPORTED_VERSION[:HEADER_PEEK_LENGTH],
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=ArtifactEncryption.UNREADABLE, reason=UnreadableReason.UNSUPPORTED_FORMAT),
    ),
    HeaderCase(
        name="magic_only",
        header=b"IHSE",
        key=KEY,
        encryption_enabled=True,
        expected=EncryptionCheck(encryption=ArtifactEncryption.UNREADABLE, reason=UnreadableReason.UNSUPPORTED_FORMAT),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in HEADER_CASES])
def test_header_tells_the_encryption_of_a_stored_object(case: HeaderCase) -> None:
    assert check_header(header=case.header, key=case.key, encryption_enabled=case.encryption_enabled) == case.expected
