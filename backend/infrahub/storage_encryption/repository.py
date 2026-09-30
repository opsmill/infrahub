from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.storage_encryption.queries import RecordedChecksumsQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class StoredObjectRepository:
    """Database access for what artifacts and file objects recorded about the objects they store."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_recorded_checksums(self, identifier: str) -> frozenset[str]:
        """Return every checksum recorded for the object stored under `identifier`, empty when none."""
        query = await RecordedChecksumsQuery.init(db=self.db, identifier=identifier)
        await query.execute(db=self.db)
        return query.get_checksums()
