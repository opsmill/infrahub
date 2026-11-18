from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from infrahub.artifacts.queries import ArtifactChecksumsQuery
from infrahub.exceptions import ArtifactChecksumMismatchError, ArtifactChecksumMissingError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.database import InfrahubDatabase
    from infrahub.storage import InfrahubObjectStorage

log = get_logger()


class ArtifactContentReader:
    """Read stored content, refusing an artifact file that does not match the checksum recorded for it.

    With `verify_checksum` off, content is returned without any check.
    """

    def __init__(self, db: InfrahubDatabase, storage: InfrahubObjectStorage, verify_checksum: bool) -> None:
        self.db = db
        self.storage = storage
        self.verify_checksum = verify_checksum

    async def read_artifact(self, storage_id: str, checksum: str | None) -> bytes:
        """Return the file stored under `storage_id` for an artifact whose recorded checksum is `checksum`.

        Raises:
            NodeNotFoundError: If nothing is stored under `storage_id`.
            ArtifactChecksumMissingError: If the artifact records no checksum.
            ArtifactChecksumMismatchError: If the stored content does not match the checksum.

        """
        content = self.storage.retrieve_binary(identifier=storage_id)
        if not self.verify_checksum:
            return content
        # Generation always records a checksum with the file, so a file without one was set by hand and cannot be checked.
        if not checksum:
            log.warning("Refused to serve an artifact file that has no recorded checksum", storage_id=storage_id)
            raise ArtifactChecksumMissingError(storage_id=storage_id)
        self._check(storage_id=storage_id, content=content, checksums={checksum})
        return content

    async def read_stored_object(self, storage_id: str) -> bytes:
        """Return the content stored under `storage_id`, checked against the checksums artifacts recorded with it.

        Content that no artifact records a checksum for is returned as it is.

        Raises:
            NodeNotFoundError: If nothing is stored under `storage_id`.
            ArtifactChecksumMismatchError: If the stored content does not match the recorded checksums.

        """
        content = self.storage.retrieve_binary(identifier=storage_id)
        if not self.verify_checksum:
            return content
        checksums = await self._get_recorded_checksums(storage_id=storage_id)
        if checksums:
            self._check(storage_id=storage_id, content=content, checksums=checksums)
        return content

    @staticmethod
    def _check(storage_id: str, content: bytes, checksums: Collection[str]) -> None:
        if hashlib.md5(content, usedforsecurity=False).hexdigest() not in checksums:
            log.warning("Refused to serve an artifact file that does not match its checksum", storage_id=storage_id)
            raise ArtifactChecksumMismatchError(storage_id=storage_id)

    async def _get_recorded_checksums(self, storage_id: str) -> frozenset[str]:
        query = await ArtifactChecksumsQuery.init(db=self.db, storage_id=storage_id)
        await query.execute(db=self.db)
        return query.get_data().checksums
