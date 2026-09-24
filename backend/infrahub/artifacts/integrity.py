"""Integrity verification of the content Infrahub reads back from its object storage.

The checksum of an artifact or a file object is recorded in the database, while its content lives in
the object storage (local filesystem or S3). The two are separate trust domains: anyone able to write
to the storage could otherwise change what Infrahub serves. Content is compared against its recorded
checksum before it leaves the API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cachetools import LRUCache

from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.protocols import CoreArtifact, CoreArtifactDefinition
from infrahub.core.query.artifact import ArtifactStorageChecksumQuery, RecordedArtifactChecksum
from infrahub.exceptions import StorageObjectIntegrityError
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.log import get_logger
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.auth.session import AccountSession
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

    ChecksumLookup = Callable[[InfrahubDatabase, str], Awaitable[list[RecordedArtifactChecksum]]]

log = get_logger()

ARTIFACT_LABEL = "artifact"
FILE_OBJECT_LABEL = "file"
REGENERATION_REQUEST_INTERVAL = 300
"""Seconds during which further failed reads of the same artifact do not request another regeneration."""


def verify_content(
    storage_id: str,
    content: bytes,
    expected_checksums: set[str | None],
    compute: Callable[[bytes], str],
    object_label: str,
) -> None:
    """Check content read from the storage against the checksums recorded for it.

    Raises:
        StorageObjectIntegrityError: If the content matches none of the recorded checksums.

    """
    actual = compute(content)
    if actual in expected_checksums:
        return
    log.error(
        "Storage object failed its integrity check",
        storage_id=storage_id,
        object_label=object_label,
        expected_checksums=sorted(str(checksum) for checksum in expected_checksums),
        actual_checksum=actual,
    )
    checksum_missing = not any(checksum is not None for checksum in expected_checksums)
    raise StorageObjectIntegrityError(
        storage_id=storage_id, object_label=object_label, checksum_missing=checksum_missing
    )


async def lookup_recorded_checksums(db: InfrahubDatabase, storage_id: str) -> list[RecordedArtifactChecksum]:
    query = await ArtifactStorageChecksumQuery.init(db=db, storage_id=storage_id)
    await query.execute(db=db)
    return query.get_recorded_checksums()


class ArtifactChecksumResolver:
    """Resolve the checksums recorded for an artifact storage object, caching resolved lookups.

    Every upload gets a new storage_id and the checksum recorded with it never changes afterwards, so a
    resolved lookup is cached without expiry. A lookup that finds nothing is not cached: the object may
    belong to an artifact whose save has not landed yet. The cache lives in process memory rather than
    in the shared cache, so the checksums it trusts cannot be planted through Redis or NATS.
    """

    def __init__(self, lookup: ChecksumLookup = lookup_recorded_checksums, cache_size: int = 100_000) -> None:
        self._lookup = lookup
        self._checksums: LRUCache[str, list[RecordedArtifactChecksum]] = LRUCache(maxsize=cache_size)

    async def get_recorded_checksums(self, db: InfrahubDatabase, storage_id: str) -> list[RecordedArtifactChecksum]:
        """Return the checksums recorded for a storage object, empty when no artifact references it."""
        if cached := self._checksums.get(storage_id):
            return cached
        recorded = await self._lookup(db, storage_id)
        if recorded:
            self._checksums[storage_id] = recorded
        return recorded


_resolver = ArtifactChecksumResolver()


def get_artifact_checksum_resolver() -> ArtifactChecksumResolver:
    return _resolver


async def request_artifact_regeneration(
    db: InfrahubDatabase, service: InfrahubServices, account: AccountSession, recorded: list[RecordedArtifactChecksum]
) -> None:
    """Queue the regeneration of the artifacts whose stored content failed its integrity check.

    Every read of a corrupted artifact fails its check; only the first one within the request interval,
    across every API server, queues a regeneration. A request that could not be queued releases its
    claim, so the next failed read tries again. Best effort: the corrupted content is refused whether or
    not the regeneration could be queued.
    """
    for artifact in recorded:
        if artifact.kind != InfrahubKind.ARTIFACT:
            continue
        key = f"artifact_regeneration_request:{artifact.branch}:{artifact.node_id}"
        # A best-effort side effect that must not replace the integrity error returned to the caller.
        try:
            claimed = await service.cache.set(
                key=key, value="requested", expires=REGENERATION_REQUEST_INTERVAL, not_exists=True
            )
            if not claimed:
                continue
            try:
                await _submit_artifact_regeneration(
                    db=db, service=service, account=account, artifact_id=artifact.node_id, branch_name=artifact.branch
                )
            except Exception:
                await service.cache.delete(key=key)
                raise
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Unable to queue the regeneration of a corrupted artifact",
                artifact_id=artifact.node_id,
                branch=artifact.branch,
                error=str(exc),
            )


async def _submit_artifact_regeneration(
    db: InfrahubDatabase, service: InfrahubServices, account: AccountSession, artifact_id: str, branch_name: str
) -> None:
    branch = await registry.get_branch(db=db, branch=branch_name)
    context = InfrahubContext.init(branch=branch, account=account)
    artifact = await registry.manager.get_one_by_id_or_default_filter(
        db=db, id=artifact_id, kind=CoreArtifact, branch=branch
    )
    definition = await artifact.definition.get_peer(db=db, peer_type=CoreArtifactDefinition, raise_on_error=True)
    await service.workflow.submit_workflow(
        workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
        context=context,
        parameters={
            "model": RequestArtifactDefinitionGenerate(
                artifact_definition_id=definition.id,
                artifact_definition_name=definition.name.value,
                branch=branch.name,
                limit=[artifact.id],
            )
        },
    )
