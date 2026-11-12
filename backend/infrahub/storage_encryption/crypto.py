"""Authenticated encryption of stored objects, keyed from the deployment's security secret.

Each object is sealed with AES-256-GCM into a self-describing envelope::

    magic (4) | format version (1) | key fingerprint (8) | nonce (12) | ciphertext and tag

The header and the object's storage identifier are authenticated as associated data, so an envelope
that is altered, truncated or copied to another identifier fails to open.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from infrahub.exceptions import StorageEncryptionError, StorageIntegrityError

if TYPE_CHECKING:
    from infrahub.config import SecuritySettings, StorageSettings

MAGIC = b"IHSE"
FORMAT_VERSION = 1
FINGERPRINT_LENGTH = 8
NONCE_LENGTH = 12
TAG_LENGTH = 16
HEADER_LENGTH = len(MAGIC) + 1 + FINGERPRINT_LENGTH + NONCE_LENGTH
_FINGERPRINT_OFFSET = len(MAGIC) + 1

_KDF_SALT = b"infrahub-storage-encryption"
_KEY_INFO = b"infrahub storage encryption key v1"
_FINGERPRINT_INFO = b"infrahub storage encryption key fingerprint v1"

MINIMUM_SECRET_LENGTH = 32
PUBLISHED_SECRET_KEYS = frozenset(
    {
        # Default of the example deployment files and documentation: anyone can derive the key from it.
        "327f747f-efac-42be-9e73-999f08f86b92",
    }
)


class IntegrityFailure(StrEnum):
    UNKNOWN_KEY = "unknown_key"
    TAMPERED = "tampered"
    UNSUPPORTED_FORMAT = "unsupported_format"
    CHECKSUM_MISMATCH = "checksum_mismatch"


@dataclass(frozen=True)
class StorageKey:
    """An AES-256-GCM key derived from a secret, and the non-secret fingerprint that identifies it."""

    fingerprint: str
    """Hex identifier of the key, written in each envelope header."""

    _fingerprint: bytes = field(repr=False)
    _cipher: AESGCM = field(repr=False, compare=False)

    @classmethod
    def derive(cls, secret: str) -> StorageKey:
        material = secret.encode("utf-8")
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=_KDF_SALT, info=_KEY_INFO).derive(material)
        fingerprint = HKDF(
            algorithm=hashes.SHA256(), length=FINGERPRINT_LENGTH, salt=_KDF_SALT, info=_FINGERPRINT_INFO
        ).derive(material)
        return cls(fingerprint=fingerprint.hex(), _fingerprint=fingerprint, _cipher=AESGCM(key))


def _unfit_secret_reason(settings: SecuritySettings) -> str | None:
    """Why INFRAHUB_SECURITY_SECRET_KEY cannot be used as the storage key, or None when it can."""
    if "secret_key" not in settings.model_fields_set:
        return (
            "Storage encryption requires INFRAHUB_STORAGE_ENCRYPTION_KEY or INFRAHUB_SECURITY_SECRET_KEY to be set, "
            "with the same value on every API server; without either, each process generates its own random secret"
        )
    if settings.secret_key.strip().strip("'\"").lower() in PUBLISHED_SECRET_KEYS:
        return (
            "INFRAHUB_SECURITY_SECRET_KEY still has the value published in Infrahub's example deployment files; "
            "set a unique random secret, or set INFRAHUB_STORAGE_ENCRYPTION_KEY, before using storage encryption"
        )
    if len(settings.secret_key) < MINIMUM_SECRET_LENGTH:
        return (
            f"INFRAHUB_SECURITY_SECRET_KEY must be at least {MINIMUM_SECRET_LENGTH} characters long to be used for "
            "storage encryption, unless INFRAHUB_STORAGE_ENCRYPTION_KEY is set"
        )
    return None


def _unfit_dedicated_key_reason(key: str) -> str | None:
    """Why INFRAHUB_STORAGE_ENCRYPTION_KEY cannot be used as the storage key, or None when it can."""
    if len(key) < MINIMUM_SECRET_LENGTH:
        return f"INFRAHUB_STORAGE_ENCRYPTION_KEY must be at least {MINIMUM_SECRET_LENGTH} characters long"
    return None


def _unfit_key_reason(storage: StorageSettings, security: SecuritySettings) -> str | None:
    """Why the key that applies cannot be used for storage encryption, or None when it can.

    A dedicated INFRAHUB_STORAGE_ENCRYPTION_KEY takes precedence, and an unfit one is never replaced by
    INFRAHUB_SECURITY_SECRET_KEY, since that would encrypt with a key the operator did not choose.
    """
    if storage.encryption_key is not None:
        return _unfit_dedicated_key_reason(storage.encryption_key.get_secret_value())
    return _unfit_secret_reason(security)


def _key_material(storage: StorageSettings, security: SecuritySettings) -> str:
    if storage.encryption_key is not None:
        return storage.encryption_key.get_secret_value()
    return security.secret_key


def storage_key_from_settings(*, storage: StorageSettings, security: SecuritySettings) -> StorageKey:
    """Derive the storage key from INFRAHUB_STORAGE_ENCRYPTION_KEY, or from INFRAHUB_SECURITY_SECRET_KEY without it.

    Raises:
        StorageEncryptionError: If the key that applies is not set explicitly, is a published example value, or is
            too short.

    """
    reason = _unfit_key_reason(storage=storage, security=security)
    if reason is not None:
        raise StorageEncryptionError(reason)
    return StorageKey.derive(_key_material(storage=storage, security=security))


def storage_key_if_set(*, storage: StorageSettings, security: SecuritySettings) -> StorageKey | None:
    """Derive the storage key when Infrahub would accept the key that applies for encryption.

    Used to read files that were encrypted earlier after encryption was turned off. Encryption refuses a key that
    is generated, published or too short, so no file can have been encrypted with one, and a key derived from such
    a secret would only let anyone who knows it forge an encrypted file. Returns None for those.
    """
    if _unfit_key_reason(storage=storage, security=security) is not None:
        return None
    return StorageKey.derive(_key_material(storage=storage, security=security))


def has_envelope_magic(content: bytes) -> bool:
    """Whether `content` starts like an envelope, even a truncated one or one of an unsupported version."""
    return content.startswith(MAGIC)


def is_envelope(content: bytes) -> bool:
    """Whether `content` is a complete envelope of the supported format."""
    return (
        len(content) >= HEADER_LENGTH + TAG_LENGTH
        and has_envelope_magic(content)
        and content[len(MAGIC)] == FORMAT_VERSION
    )


def is_sealed_with(content: bytes, key: StorageKey) -> bool:
    """Whether the header of the envelope in `content` names `key`; the content is not authenticated."""
    return content[_FINGERPRINT_OFFSET : _FINGERPRINT_OFFSET + FINGERPRINT_LENGTH] == key._fingerprint


def seal(*, identifier: str, content: bytes, key: StorageKey) -> bytes:
    nonce = os.urandom(NONCE_LENGTH)
    header = MAGIC + bytes((FORMAT_VERSION,)) + key._fingerprint + nonce
    return header + key._cipher.encrypt(nonce, content, header + identifier.encode("utf-8"))


def open_envelope(*, identifier: str, content: bytes, key: StorageKey) -> bytes:
    """Authenticate an envelope stored under `identifier` and return its content.

    Raises:
        StorageIntegrityError: If the envelope is truncated, has an unsupported format, was sealed with another
            key or fails authentication.

    """
    if len(content) <= len(MAGIC) or content[len(MAGIC)] != FORMAT_VERSION:
        raise StorageIntegrityError(identifier=identifier, reason=IntegrityFailure.UNSUPPORTED_FORMAT)
    if len(content) < HEADER_LENGTH + TAG_LENGTH:
        raise StorageIntegrityError(identifier=identifier, reason=IntegrityFailure.TAMPERED)
    if content[_FINGERPRINT_OFFSET : _FINGERPRINT_OFFSET + FINGERPRINT_LENGTH] != key._fingerprint:
        raise StorageIntegrityError(identifier=identifier, reason=IntegrityFailure.UNKNOWN_KEY)
    header = content[:HEADER_LENGTH]
    try:
        return key._cipher.decrypt(
            header[-NONCE_LENGTH:], memoryview(content)[HEADER_LENGTH:], header + identifier.encode("utf-8")
        )
    except InvalidTag as exc:
        raise StorageIntegrityError(identifier=identifier, reason=IntegrityFailure.TAMPERED) from exc
