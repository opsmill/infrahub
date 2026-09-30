from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.registry import registry
from infrahub.exceptions import StorageIntegrityError
from infrahub.log import get_logger
from infrahub.storage_encryption.checksums import matches_recorded_checksum
from infrahub.storage_encryption.crypto import IntegrityFailure
from infrahub.storage_encryption.repository import StoredObjectRepository

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


async def read_stored_object(db: InfrahubDatabase, identifier: str, recorded_checksum: str | None) -> bytes:
    """Return the content of a stored object, refusing it when storage encryption is on and it fails its check.

    An encrypted object is authenticated as it is decrypted. An object stored before encryption was
    enabled must match its recorded checksum: `recorded_checksum` when the caller has it, otherwise
    the checksums the database recorded with `identifier`. One that nothing records a checksum for is
    returned as it is.

    Raises:
        NodeNotFoundError: If no object is stored under `identifier`.
        StorageIntegrityError: If the object fails its integrity check.

    """
    try:
        stored = await asyncio.to_thread(registry.storage.read, identifier)
    except StorageIntegrityError as exc:
        log.warning("Refused a stored object that failed its integrity check", storage_id=identifier, reason=exc.reason)
        raise
    if stored.authenticated or not config.SETTINGS.storage.encryption_enabled:
        return stored.content
    checksums = (
        {recorded_checksum}
        if recorded_checksum
        else await StoredObjectRepository(db=db).get_recorded_checksums(identifier=identifier)
    )
    if matches_recorded_checksum(content=stored.content, checksums=checksums) is False:
        log.warning(
            "Refused a stored object that failed its integrity check",
            storage_id=identifier,
            reason=IntegrityFailure.CHECKSUM_MISMATCH,
        )
        raise StorageIntegrityError(identifier=identifier, reason=IntegrityFailure.CHECKSUM_MISMATCH)
    return stored.content
