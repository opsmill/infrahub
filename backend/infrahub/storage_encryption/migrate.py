"""Encrypt the stored objects that were written before storage encryption was enabled.

This module does not choose which objects to encrypt, in which order or how often: a caller walks the storage and
hands identifiers over in groups. Typical use::

    results = await encrypt_stored_objects(
        db=db, storage=storage, identifiers=identifiers, max_size=limit, budget=budget, wait_seconds=1.0
    )

Encrypting an object is safe to repeat and safe to interrupt: an object that is already encrypted is left as it is,
and the object is replaced in one atomic step, so it is always either the previous file or the encrypted one.
Readers need no change, since reading decrypts an encrypted object and serves any other as it is.

The steps for one object, each of which can end the work:

1. Read the first bytes. An object whose header names the current key is `already_encrypted`; its content is not
   authenticated here. An object that starts like an encrypted one but cannot be read with the current key
   (another key, truncated, unsupported format) is `failed`. Nothing is ever encrypted twice.
2. Look up the checksums that nodes recorded for the object, for the whole group in two database queries.
3. Read the object. One larger than the limit is `skipped_too_large` and is not read. The content is compared with
   the checksums: MD5 for the 32-character ones, SHA-1 for the 40-character ones. No match is
   `skipped_checksum_mismatch`. Nothing to compare with is `skipped_unverified`, unless the caller accepts
   unverified content.
4. Seal the content with the storage key, replace the object atomically, then read the header again to confirm
   that the stored object is encrypted with the current key.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import botocore.exceptions

from infrahub.core.constants import ArtifactEncryption, InfrahubKind
from infrahub.exceptions import NodeNotFoundError, StorageEncryptionError
from infrahub.log import get_logger
from infrahub.storage_encryption.checksums import matches_recorded_checksum
from infrahub.storage_encryption.crypto import has_envelope_magic, seal
from infrahub.storage_encryption.queries import StorageChecksumsQuery

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.database import InfrahubDatabase
    from infrahub.storage import InfrahubObjectStorage
    from infrahub.storage_encryption.crypto import StorageKey
    from infrahub.storage_encryption.memory_budget import MemoryBudget

log = get_logger()

HEADER_REQUEST_LENGTH = 4096
"""Bytes a header read from S3 asks for: a ranged read shorter than about 1,400 bytes can wait 40 ms on some services."""


STORAGE_ERRORS = (OSError, botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError)
"""What the storage raises for a read or a write that fails: a file system error, a refusal of the S3 service, or a broken connection."""


class EncryptOutcome(StrEnum):
    ENCRYPTED = "encrypted"
    """The object was not encrypted and now is."""
    ALREADY_ENCRYPTED = "already_encrypted"
    """The header of the object names the current key; the object was left as it is."""
    SKIPPED_TOO_LARGE = "skipped_too_large"
    """The object is larger than the size the caller accepts to hold in memory; it was not read."""
    SKIPPED_UNVERIFIED = "skipped_unverified"
    """No node records a checksum that can prove the object unchanged, and the caller did not accept that."""
    SKIPPED_CHECKSUM_MISMATCH = "skipped_checksum_mismatch"
    """The object matches none of the checksums recorded for it, so it was modified outside Infrahub."""
    MISSING = "missing"
    """Nothing is stored under the identifier."""
    FAILED = "failed"
    """The object could not be encrypted; the reason says why."""


@dataclass(frozen=True)
class EncryptResult:
    """What happened to one stored object."""

    identifier: str
    outcome: EncryptOutcome

    size: int = 0
    """Size in bytes of the object before the call, or 0 when it was not measured (missing or already encrypted)."""

    reason: str | None = None
    """Why the object was not encrypted, for the outcomes that need an explanation."""


def require_encryption_ready(storage: InfrahubObjectStorage) -> StorageKey:
    """Return the key existing objects are encrypted with, after checking that encrypting them makes sense.

    Raises:
        StorageEncryptionError: If the storage has no key, or if storage encryption is disabled.

    """
    if storage.key is None:
        raise StorageEncryptionError(
            "Existing stored objects cannot be encrypted because this process has no storage key; run it where "
            "INFRAHUB_STORAGE_ENCRYPTION_KEY or INFRAHUB_SECURITY_SECRET_KEY is set, as on the API server"
        )
    if not storage.encryption_enabled:
        raise StorageEncryptionError(
            "Existing stored objects are not encrypted while storage encryption is disabled, because new files "
            "would still be stored unencrypted; set INFRAHUB_STORAGE_ENCRYPTION_ENABLED to true first"
        )
    return storage.key


def _failed(identifier: str, reason: str, size: int = 0) -> EncryptResult:
    return EncryptResult(identifier=identifier, outcome=EncryptOutcome.FAILED, size=size, reason=reason)


def _failed_by_storage(identifier: str, reason: str, exc: Exception, size: int = 0) -> EncryptResult:
    # The caller gets a fixed reason: the error text can hold a local path or the raw answer of the S3 service.
    log.warning(f"Stored object encryption failed: {reason}", identifier=identifier, error=str(exc))
    return _failed(identifier=identifier, reason=reason, size=size)


def precheck_object(storage: InfrahubObjectStorage, identifier: str) -> EncryptResult | None:
    """Read the header of an object and return its result when it needs no further work, otherwise None.

    An object that is encrypted, missing or unreadable needs nothing else, so it costs no database query.
    """
    try:
        check = storage.inspect_encryption(identifier=identifier, request_length=HEADER_REQUEST_LENGTH)
    except STORAGE_ERRORS as exc:
        return _failed_by_storage(identifier=identifier, reason="the header could not be read", exc=exc)
    if check.encryption is None:
        return EncryptResult(identifier=identifier, outcome=EncryptOutcome.MISSING)
    if check.encryption is ArtifactEncryption.ENCRYPTED:
        return EncryptResult(identifier=identifier, outcome=EncryptOutcome.ALREADY_ENCRYPTED)
    if check.encryption is ArtifactEncryption.UNREADABLE:
        return _failed(
            identifier=identifier, reason=f"the object starts like an encrypted one but is unreadable: {check.reason}"
        )
    return None


def _stop_on_checksums(
    identifier: str, content: bytes, checksums: Collection[str] | None, allow_unverified: bool
) -> EncryptResult | None:
    matches = matches_recorded_checksum(content=content, checksums=checksums or ())
    if matches is False:
        return EncryptResult(
            identifier=identifier,
            outcome=EncryptOutcome.SKIPPED_CHECKSUM_MISMATCH,
            size=len(content),
            reason="the content matches none of the checksums recorded for it",
        )
    if matches is None and not allow_unverified:
        return EncryptResult(
            identifier=identifier,
            outcome=EncryptOutcome.SKIPPED_UNVERIFIED,
            size=len(content),
            reason="no checksum is recorded for this object",
        )
    return None


def _seal_and_replace(
    storage: InfrahubObjectStorage, identifier: str, content: bytes, key: StorageKey
) -> EncryptResult:
    size = len(content)
    try:
        storage.replace(identifier=identifier, content=seal(identifier=identifier, content=content, key=key))
        check = storage.inspect_encryption(identifier=identifier, request_length=HEADER_REQUEST_LENGTH)
    except NodeNotFoundError:
        return EncryptResult(identifier=identifier, outcome=EncryptOutcome.MISSING)
    except STORAGE_ERRORS as exc:
        return _failed_by_storage(identifier=identifier, size=size, reason="the object could not be replaced", exc=exc)
    if check.encryption is not ArtifactEncryption.ENCRYPTED:
        return _failed(
            identifier=identifier, size=size, reason="the object does not read back as encrypted after the write"
        )
    return EncryptResult(identifier=identifier, outcome=EncryptOutcome.ENCRYPTED, size=size)


def encrypt_object(
    storage: InfrahubObjectStorage,
    identifier: str,
    checksums: Collection[str] | None,
    max_size: int,
    budget: MemoryBudget,
    wait_seconds: float,
    allow_unverified: bool = False,
) -> EncryptResult:
    """Encrypt an object whose header was already checked: one read, one write, one header read to confirm.

    The size limit is applied to the size the storage reports with the content, before the content is read, and
    it is the smaller of `max_size` and the largest object the memory budget can hold. The memory for the
    content is claimed before it is read and released once the encrypted copy is written, so an object that does
    not fit in the free memory within `wait_seconds` is not read. An object that another writer encrypted since
    the header check is recognised from the bytes read.

    This function blocks on storage I/O, so call it from a thread when an event loop is running. Two concurrent
    calls on the same object are harmless: both seal the same content and the last write wins.

    Args:
        storage: The storage that holds the object. It must have a key and have encryption enabled.
        identifier: The storage identifier of the object.
        checksums: Every checksum recorded for this identifier, or None when they are not known.
        max_size: Largest object, in bytes, that is read and encrypted.
        budget: The memory the process may use to hold objects while it encrypts them.
        wait_seconds: How long to wait for the budget to have room for the object.
        allow_unverified: Encrypt an object that has no comparable checksum instead of skipping it.

    Raises:
        StorageEncryptionError: If the storage has no key, or if storage encryption is disabled.
        MemoryBudgetBusyError: If the memory the object needs is not free within `wait_seconds`.

    """
    key = require_encryption_ready(storage=storage)
    limit = min(max_size, budget.largest_object)
    with budget.holding(wait_seconds=wait_seconds) as hold:
        try:
            stored = storage.read_stored_bounded(identifier=identifier, max_size=limit, before_read=hold.take)
        except STORAGE_ERRORS as exc:
            return _failed_by_storage(identifier=identifier, reason="the object could not be read", exc=exc)
        if stored is None:
            return EncryptResult(identifier=identifier, outcome=EncryptOutcome.MISSING)
        size, content = stored
        if content is None:
            return EncryptResult(
                identifier=identifier,
                outcome=EncryptOutcome.SKIPPED_TOO_LARGE,
                size=size,
                reason=f"{size} bytes is more than the limit of {limit} bytes",
            )
        if has_envelope_magic(content):
            # Another writer encrypted the object after its header was read; the header check decides what it is.
            again = precheck_object(storage=storage, identifier=identifier)
            return again or _failed(identifier=identifier, reason="the object changed while it was read")
        stopped = _stop_on_checksums(
            identifier=identifier, content=content, checksums=checksums, allow_unverified=allow_unverified
        )
        if stopped is not None:
            return stopped
        return _seal_and_replace(storage=storage, identifier=identifier, content=content, key=key)


async def get_recorded_checksums(db: InfrahubDatabase, storage_ids: list[str]) -> dict[str, frozenset[str]]:
    """Return every checksum recorded for each identifier, by artifacts and by file objects, in two queries.

    All branches and the whole history are covered, so the file of an earlier artifact version, of a deleted
    node or of a branch that was never merged still finds its checksum. Artifacts record an MD5 digest and file
    objects a SHA-1 digest. An identifier no node ever referred to maps to an empty set.
    """
    merged: dict[str, frozenset[str]] = {storage_id: frozenset() for storage_id in storage_ids}
    if not storage_ids:
        return merged
    for kind in (InfrahubKind.ARTIFACT, InfrahubKind.FILEOBJECT):
        query = await StorageChecksumsQuery.init(db=db, storage_ids=storage_ids, kind=kind)
        await query.execute(db=db)
        for storage_id, checksums in query.get_data().items():
            merged[storage_id] = merged.get(storage_id, frozenset()) | checksums
    return merged


async def encrypt_stored_objects(
    db: InfrahubDatabase,
    storage: InfrahubObjectStorage,
    identifiers: list[str],
    max_size: int,
    budget: MemoryBudget,
    wait_seconds: float,
    allow_unverified: bool = False,
) -> list[EncryptResult]:
    """Encrypt stored objects one after the other and return one result per identifier, in the order given.

    The storage I/O runs in worker threads, so the event loop stays free while objects are read and written. The
    module description gives the steps and their outcomes; `wait_seconds` is how long one object waits for the
    memory budget to have room for it.

    Raises:
        StorageEncryptionError: If the storage has no key, or if storage encryption is disabled.
        MemoryBudgetBusyError: If an object waited `wait_seconds` for memory and none was free.

    """
    require_encryption_ready(storage=storage)
    results: dict[str, EncryptResult] = {}
    for identifier in identifiers:
        stopped = await asyncio.to_thread(precheck_object, storage, identifier)
        if stopped is not None:
            results[identifier] = stopped
    pending = [identifier for identifier in identifiers if identifier not in results]
    checksums = await get_recorded_checksums(db=db, storage_ids=pending)
    for identifier in pending:
        results[identifier] = await asyncio.to_thread(
            encrypt_object, storage, identifier, checksums[identifier], max_size, budget, wait_seconds, allow_unverified
        )
    return [results[identifier] for identifier in identifiers]
