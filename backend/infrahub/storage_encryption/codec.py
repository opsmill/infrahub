"""Turn the content written to the storage into stored bytes, and stored bytes back into content.

The storage driver only moves bytes. A codec decides what is written and what a stored object means, so that the
encryption lives in one place and can be replaced without touching the storage.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, BinaryIO, Protocol

from infrahub.exceptions import StorageEncryptionError, StorageIntegrityError
from infrahub.log import get_logger
from infrahub.storage_encryption.crypto import (
    StorageKey,
    has_envelope_magic,
    is_envelope,
    open_envelope,
    seal,
    storage_key_from_settings,
)

if TYPE_CHECKING:
    from infrahub.config import SecuritySettings, StorageSettings

log = get_logger()

_ENABLED_WITHOUT_KEY = (
    "Storage encryption is enabled but this process has no key; only the API server reads and writes stored objects"
)


@dataclass(frozen=True)
class StoredContent:
    content: bytes

    authenticated: bool
    """Whether the content was decrypted from an envelope that proved it unchanged."""


class StoredContentCodec(Protocol):
    """Turns content into what is written to the storage, and what was read from it back into content."""

    def encode(self, identifier: str, content: BinaryIO) -> BinaryIO:
        """Return the stream to write for `content`, stored under `identifier`."""
        ...

    def decode(self, identifier: str, stored: bytes) -> StoredContent:
        """Return the content that the bytes read from the object `identifier` stand for."""
        ...


class AesGcmCodec:
    """Encryption on: encrypts every write, and decrypts every object that starts with the marker."""

    def __init__(self, key: StorageKey) -> None:
        self._key = key

    def encode(self, identifier: str, content: BinaryIO) -> BinaryIO:
        content.seek(0)
        return io.BytesIO(seal(identifier=identifier, content=content.read(), key=self._key))

    def decode(self, identifier: str, stored: bytes) -> StoredContent:
        if not has_envelope_magic(stored):
            return StoredContent(content=stored, authenticated=False)
        try:
            content = open_envelope(identifier=identifier, content=stored, key=self._key)
        except StorageIntegrityError as exc:
            log.warning(
                "Refused a stored object that failed its integrity check",
                storage_id=identifier,
                reason=exc.reason,
                key_fingerprint=self._key.fingerprint,
            )
            raise
        return StoredContent(content=content, authenticated=True)


class DecryptOnlyCodec:
    """Encryption off, key still usable: writes the content as it is, and decrypts what was encrypted before."""

    def __init__(self, decrypter: AesGcmCodec) -> None:
        self._decrypter = decrypter

    def encode(self, identifier: str, content: BinaryIO) -> BinaryIO:  # noqa: ARG002
        return content

    def decode(self, identifier: str, stored: bytes) -> StoredContent:
        # Only a complete envelope counts, so plain files that start with the marker are still served.
        if is_envelope(stored):
            return self._decrypter.decode(identifier=identifier, stored=stored)
        return StoredContent(content=stored, authenticated=False)


class PlainCodec:
    """Encryption off, no usable key: writes the content as it is, and refuses encrypted files."""

    def encode(self, identifier: str, content: BinaryIO) -> BinaryIO:  # noqa: ARG002
        return content

    def decode(self, identifier: str, stored: bytes) -> StoredContent:
        if is_envelope(stored):
            raise StorageEncryptionError(
                f"The stored object {identifier} is encrypted but this process has no key to decrypt it; set "
                "INFRAHUB_STORAGE_ENCRYPTION_KEY, or INFRAHUB_SECURITY_SECRET_KEY when no dedicated key was used, to "
                "the value that was in use when encryption was enabled"
            )
        return StoredContent(content=stored, authenticated=False)


class NoKeyCodec:
    """Encryption on, but no key in this process: refuses to write, and to read an encrypted file."""

    def encode(self, identifier: str, content: BinaryIO) -> BinaryIO:  # noqa: ARG002
        raise StorageEncryptionError(_ENABLED_WITHOUT_KEY)

    def decode(self, identifier: str, stored: bytes) -> StoredContent:  # noqa: ARG002
        if has_envelope_magic(stored):
            raise StorageEncryptionError(_ENABLED_WITHOUT_KEY)
        return StoredContent(content=stored, authenticated=False)


def select_codec(*, encryption_enabled: bool, key: StorageKey | None) -> StoredContentCodec:
    """Pick the codec for the encryption setting and the key a process has, if any."""
    if key is None:
        return NoKeyCodec() if encryption_enabled else PlainCodec()
    decrypter = AesGcmCodec(key)
    return decrypter if encryption_enabled else DecryptOnlyCodec(decrypter)


def build_storage_codec(storage: StorageSettings, security: SecuritySettings) -> StoredContentCodec:
    """Build the codec of the API server from the settings.

    Raises:
        StorageEncryptionError: If encryption is enabled and the key that applies cannot be used.

    """
    return select_codec(
        encryption_enabled=storage.encryption_enabled,
        key=storage_key_from_settings(storage=storage, security=security),
    )
