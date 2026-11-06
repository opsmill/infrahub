from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.artifacts.queries import ArtifactChecksumsQuery
from infrahub.core import registry
from infrahub.exceptions import ArtifactChecksumMismatchError, ArtifactChecksumMissingError, StorageIntegrityError
from infrahub.log import get_logger
from infrahub.storage_encryption.checksums import matches_recorded_checksum
from infrahub.storage_encryption.crypto import IntegrityFailure

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.database import InfrahubDatabase
    from infrahub.storage import InfrahubObjectStorage

log = get_logger()


def get_artifact_content_reader(db: InfrahubDatabase) -> ArtifactContentReader:
    """Build the reader of the configured storage.

    While storage encryption is enabled, content that was stored before it was enabled is always checked
    against its recorded checksum, whatever `verify_artifact_checksum` says.
    """
    settings = config.SETTINGS.storage
    return ArtifactContentReader(
        db=db,
        storage=registry.storage,
        verify_checksum=settings.verify_artifact_checksum or settings.encryption_enabled,
        verify_file_objects=settings.encryption_enabled,
        trust_decrypted=settings.encryption_enabled,
    )


class ArtifactContentReader:
    """Read stored content, refusing a file that fails its integrity check.

    Content that was encrypted by Infrahub proves itself unchanged when it is decrypted, so it needs no
    checksum. Any other content is compared with the checksum recorded for it, unless `verify_checksum`
    is off, in which case it is returned without any check.

    Reading an encrypted object can also raise `StorageIntegrityError`, when it was sealed with another
    key or was modified.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        storage: InfrahubObjectStorage,
        verify_checksum: bool,
        verify_file_objects: bool,
        trust_decrypted: bool,
    ) -> None:
        """Create a reader.

        `verify_file_objects` turns on the checksum check of file objects stored before storage encryption
        was enabled. File objects are not checked otherwise. `trust_decrypted` serves content that decrypted
        without a checksum check; it is on only while storage encryption is enabled, as a key that is still held
        after encryption was turned off no longer proves who wrote the file.
        """
        self.db = db
        self.storage = storage
        self.verify_checksum = verify_checksum
        self.verify_file_objects = verify_file_objects
        self.trust_decrypted = trust_decrypted

    async def read_artifact(self, storage_id: str, checksum: str | None) -> bytes:
        """Return the file stored under `storage_id` for an artifact whose recorded checksum is `checksum`.

        Raises:
            NodeNotFoundError: If nothing is stored under `storage_id`.
            StorageIntegrityError: If the file is encrypted and fails authentication.
            ArtifactChecksumMissingError: If the file is not encrypted and the artifact records no checksum.
            ArtifactChecksumMismatchError: If the file is not encrypted and does not match the checksum.

        """
        stored = self.storage.read(identifier=storage_id)
        if (stored.authenticated and self.trust_decrypted) or not self.verify_checksum:
            return stored.content
        # Generation always records a checksum with the file, so a file without one was set by hand and cannot be checked.
        if not checksum:
            log.warning("Refused to serve an artifact file that has no recorded checksum", storage_id=storage_id)
            raise ArtifactChecksumMissingError(storage_id=storage_id)
        self._check(storage_id=storage_id, content=stored.content, checksums={checksum})
        return stored.content

    async def read_stored_object(self, storage_id: str) -> bytes:
        """Return the content stored under `storage_id`, checked against the checksums artifacts recorded with it.

        Content that no artifact records a checksum for is returned as it is.

        Raises:
            NodeNotFoundError: If nothing is stored under `storage_id`.
            StorageIntegrityError: If the content is encrypted and fails authentication.
            ArtifactChecksumMismatchError: If the content is not encrypted and does not match the recorded checksums.

        """
        stored = self.storage.read(identifier=storage_id)
        if (stored.authenticated and self.trust_decrypted) or not self.verify_checksum:
            return stored.content
        checksums = await self._get_recorded_checksums(storage_id=storage_id)
        if checksums:
            self._check(storage_id=storage_id, content=stored.content, checksums=checksums)
        return stored.content

    async def read_file_object(self, storage_id: str, checksum: str | None) -> bytes:
        """Return the content stored under `storage_id` for a file object whose recorded checksum is `checksum`.

        A file stored before storage encryption was enabled is returned only if it matches `checksum`. A file
        without a recorded checksum, or a checksum that cannot be compared, is returned as it is.

        Raises:
            NodeNotFoundError: If nothing is stored under `storage_id`.
            StorageIntegrityError: If the file is encrypted and fails authentication, or is not encrypted and
                does not match its checksum.

        """
        stored = self.storage.read(identifier=storage_id)
        if (stored.authenticated and self.trust_decrypted) or not self.verify_file_objects or not checksum:
            return stored.content
        if matches_recorded_checksum(content=stored.content, checksums={checksum}) is False:
            log.warning("Refused to serve a file that does not match its checksum", storage_id=storage_id)
            raise StorageIntegrityError(identifier=storage_id, reason=IntegrityFailure.CHECKSUM_MISMATCH)
        return stored.content

    @staticmethod
    def _check(storage_id: str, content: bytes, checksums: Collection[str]) -> None:
        if hashlib.md5(content, usedforsecurity=False).hexdigest() not in checksums:
            log.warning("Refused to serve an artifact file that does not match its checksum", storage_id=storage_id)
            raise ArtifactChecksumMismatchError(storage_id=storage_id)

    async def _get_recorded_checksums(self, storage_id: str) -> frozenset[str]:
        query = await ArtifactChecksumsQuery.init(db=self.db, storage_id=storage_id)
        await query.execute(db=self.db)
        return query.get_data().checksums
