"""What the header of a stored object says about its encryption, without reading or decrypting the whole object."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from infrahub.core.constants import ArtifactEncryption
from infrahub.storage_encryption.crypto import (
    FORMAT_VERSION,
    HEADER_LENGTH,
    MAGIC,
    TAG_LENGTH,
    StorageKey,
    has_envelope_magic,
    is_envelope,
    is_sealed_with,
)

HEADER_PEEK_LENGTH = HEADER_LENGTH + TAG_LENGTH
"""Bytes read from the start of an object to tell whether it is a complete envelope and which key sealed it."""


class UnreadableReason(StrEnum):
    NO_KEY = "no_key"
    UNKNOWN_KEY = "unknown_key"
    UNSUPPORTED_FORMAT = "unsupported_format"
    TRUNCATED = "truncated"
    MISSING = "missing"


@dataclass(frozen=True)
class EncryptionCheck:
    encryption: ArtifactEncryption | None
    """None when the object does not exist, so nothing can be said about its encryption."""
    reason: UnreadableReason | None


def check_header(*, header: bytes | None, key: StorageKey | None, encryption_enabled: bool) -> EncryptionCheck:
    """Classify a stored object from its first bytes.

    The header names the key that sealed the object, so this tells an object sealed with another key from one
    sealed with the current key, but it does not authenticate the content: a modified object still reports
    as encrypted until it is read in full.
    """
    if header is None:
        return EncryptionCheck(encryption=None, reason=UnreadableReason.MISSING)
    # Same rule as reading: with encryption off only a complete envelope counts as encrypted.
    is_encrypted = has_envelope_magic(header) if encryption_enabled else is_envelope(header)
    if not is_encrypted:
        return EncryptionCheck(encryption=ArtifactEncryption.PLAINTEXT, reason=None)
    reason = _unreadable_reason(header=header, key=key)
    if reason is not None:
        return EncryptionCheck(encryption=ArtifactEncryption.UNREADABLE, reason=reason)
    return EncryptionCheck(encryption=ArtifactEncryption.ENCRYPTED, reason=None)


def _unreadable_reason(*, header: bytes, key: StorageKey | None) -> UnreadableReason | None:
    """Why an encrypted object cannot be read with `key`, in the order reading checks it, or None when it can."""
    if key is None:
        return UnreadableReason.NO_KEY
    if len(header) <= len(MAGIC) or header[len(MAGIC)] != FORMAT_VERSION:
        return UnreadableReason.UNSUPPORTED_FORMAT
    if len(header) < HEADER_PEEK_LENGTH:
        return UnreadableReason.TRUNCATED
    if not is_sealed_with(header, key):
        return UnreadableReason.UNKNOWN_KEY
    return None
