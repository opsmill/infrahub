from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.uuidt import UUIDT

from infrahub.core.query.template_fingerprint import (
    TemplateFingerprintDeleteBranchQuery,
    TemplateFingerprintDeleteQuery,
    TemplateFingerprintGetByFamilyQuery,
    TemplateFingerprintInsertMissingQuery,
    TemplateFingerprintUpsertQuery,
)
from infrahub.core.template_fingerprint.models import FingerprintKey, RecordedFingerprint, TemplateFamily

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def _key_params(key: FingerprintKey) -> dict[str, str]:
    return {"family": key.family.value, "branch": key.branch, "kind": key.kind}


def _record_params(records: list[RecordedFingerprint]) -> list[dict[str, Any]]:
    # One entry per key: a duplicate would be counted twice by the insert query.
    unique = {record.key: record for record in records}
    return [
        {**_key_params(record.key), "fingerprint": record.fingerprint, "uuid": str(UUIDT())}
        for record in unique.values()
    ]


class TemplateFingerprintRepository:
    """Database access for the recorded template fingerprints.

    A write skips the records of a branch that has no Branch vertex, so a flow that runs after the branch
    was deleted cannot leave a record that a new branch with the same name would inherit.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_by_family(self, family: TemplateFamily) -> list[RecordedFingerprint]:
        query = TemplateFingerprintGetByFamilyQuery(family=family.value)
        await query.execute(db=self.db)

        return [
            RecordedFingerprint(
                key=FingerprintKey(family=family, branch=row.branch, kind=row.kind), fingerprint=row.fingerprint
            )
            for row in query.get_data()
        ]

    async def upsert(self, records: list[RecordedFingerprint]) -> None:
        if not records:
            return
        query = TemplateFingerprintUpsertQuery(records=_record_params(records))
        await query.execute(db=self.db)

    async def insert_missing(self, records: list[RecordedFingerprint]) -> int:
        """Create the records that do not exist yet, never overwrite one, and return how many were created."""
        if not records:
            return 0
        query = TemplateFingerprintInsertMissingQuery(records=_record_params(records))
        await query.execute(db=self.db)
        return sum(row.created for row in query.get_data())

    async def delete(self, keys: list[FingerprintKey]) -> None:
        if not keys:
            return
        query = TemplateFingerprintDeleteQuery(keys=[_key_params(key) for key in keys])
        await query.execute(db=self.db)

    async def delete_branch(self, branch_name: str) -> None:
        query = TemplateFingerprintDeleteBranchQuery(branch_name=branch_name)
        await query.execute(db=self.db)
