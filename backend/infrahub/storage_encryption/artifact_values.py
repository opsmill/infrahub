"""Store the encryption value of the artifacts whose file the migration encrypted or found encrypted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from neo4j.exceptions import Neo4jError

from infrahub.artifacts.encryption import may_store_artifact_encryption, store_artifact_encryption, stored_encryption
from infrahub.core import registry
from infrahub.core.constants import ArtifactEncryption
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreArtifact
from infrahub.exceptions import DatabaseError, QueryTimeoutError
from infrahub.log import get_logger
from infrahub.storage_encryption.migrate import EncryptOutcome

if TYPE_CHECKING:
    from infrahub.core.merge.write_blocker import MergeWriteBlocker
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions import PermissionManager
    from infrahub.storage_encryption.migrate import EncryptResult

log = get_logger()

ENCRYPTED_FILE_OUTCOMES = frozenset({EncryptOutcome.ENCRYPTED, EncryptOutcome.ALREADY_ENCRYPTED})
"""The outcomes that leave the object encrypted with the current key, so the artifact that points at it is `encrypted`."""


@dataclass(frozen=True)
class ArtifactValuesResult:
    """What happened to the artifacts that point at the encrypted objects of one request."""

    updated: int = 0
    """Artifacts whose stored value was changed to `encrypted`."""
    already_correct: int = 0
    """Artifacts that already stored `encrypted`."""
    failed: int = 0
    """Artifacts whose value could not be written, or objects whose artifacts could not be looked up.

    A new pass over the objects stores the value.
    """
    not_written: int = 0
    """Artifacts left as they are because the caller may not update them or the branch does not accept writes."""


async def store_encrypted_artifact_values(
    *,
    db: InfrahubDatabase,
    results: list[EncryptResult],
    permission_manager: PermissionManager,
    merge_write_blocker: MergeWriteBlocker,
    user_id: str,
) -> ArtifactValuesResult:
    """Store `encrypted` on the artifacts of the default branch whose current file is an object that is now encrypted.

    One query finds the artifacts of all objects of a request. An artifact is looked up by the identifier it points
    at now, never by an earlier version. A failure to write one artifact is logged and counted, and the other
    artifacts are still written: the object itself is encrypted, and a later pass over the same object writes the
    value again.
    """
    identifiers = [result.identifier for result in results if result.outcome in ENCRYPTED_FILE_OUTCOMES]
    if not identifiers:
        return ArtifactValuesResult()
    branch = registry.get_branch_from_registry()
    try:
        artifacts = await NodeManager.query(
            db=db, schema=CoreArtifact, branch=branch, filters={"storage_id__values": identifiers}
        )
    except (DatabaseError, QueryTimeoutError, Neo4jError) as exc:
        log.warning("Could not look up the artifacts of encrypted objects", branch=branch.name, error=str(exc))
        return ArtifactValuesResult(failed=len(identifiers))
    stale = [artifact for artifact in artifacts if stored_encryption(artifact) != ArtifactEncryption.ENCRYPTED]
    if not stale:
        return ArtifactValuesResult(already_correct=len(artifacts))
    if not await may_store_artifact_encryption(
        db=db, branch=branch, permission_manager=permission_manager, merge_write_blocker=merge_write_blocker
    ):
        log.warning("The encryption of artifacts was not stored", branch=branch.name, artifacts=len(stale))
        return ArtifactValuesResult(already_correct=len(artifacts) - len(stale), not_written=len(stale))

    updated = failed = 0
    for artifact in stale:
        try:
            await store_artifact_encryption(
                db=db, artifact=artifact, found=ArtifactEncryption.ENCRYPTED, user_id=user_id
            )
        except (DatabaseError, QueryTimeoutError, Neo4jError) as exc:
            failed += 1
            log.warning("Could not store the encryption of an artifact", artifact_id=artifact.id, error=str(exc))
        else:
            updated += 1
    if failed:
        log.warning("The encryption of some artifacts was not stored", branch=branch.name, failed=failed)
    return ArtifactValuesResult(updated=updated, already_correct=len(artifacts) - len(stale), failed=failed)
