from __future__ import annotations

import time
from itertools import batched
from typing import TYPE_CHECKING

from infrahub.core.query.rollback import (
    RollbackDeleteEdgesQuery,
    RollbackDeleteOrphanedVerticesQuery,
    RollbackReopenEdgesQuery,
    RollbackRestoreMetadataQuery,
    RollbackScope,
)
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

log = get_logger()


class GraphRollbacker:
    """Rollback database changes made on a branch at (or since) a timestamp.

    Reverses database changes by:
    1. Resetting `to` times (and `to_user_id`) back to NULL for edges that were closed
       in the rollback window.
    2. Deleting edges that were created in the rollback window.
    3. Deleting any vertices that become orphaned after the edge deletions. Only the endpoints
       of deleted edges can be orphaned — a reopened edge still connects its vertices.
    4. (Optional) Restoring the `previous_updated_at`/`previous_updated_by` snapshots on the
       vertices the rolled-back writes had bumped. Restoring is only allowed when the target
       branch is the default or global branch — vertex metadata properties are maintained solely
       for those branches, so there is nothing to restore anywhere else.

    Each phase runs as its own statement to reduce memory footprint.

    Idempotent, and resumable: each statement commits its writes in batches, so an interrupted
    rollback can be re-run to finish the remaining work.
    """

    vertex_id_batch_size = 20_000

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def rollback(
        self,
        target_branch: Branch,
        at: Timestamp,
        scope: RollbackScope,
        restore_metadata: bool,
    ) -> None:
        if restore_metadata and not (target_branch.is_default or target_branch.is_global):
            raise ValueError("restore_metadata is only allowed when the target branch is the default or global branch")

        started = time.monotonic()
        reopen_query = await RollbackReopenEdgesQuery.init(db=self.db, at=at, target_branch=target_branch, scope=scope)
        await reopen_query.execute(db=self.db)
        touched_vertex_ids = set(reopen_query.get_touched_vertex_ids())
        log.debug(
            f"Rollback reopen phase complete ({len(touched_vertex_ids)} vertices touched, "
            f"{time.monotonic() - started:.1f}s)"
        )

        started = time.monotonic()
        delete_query = await RollbackDeleteEdgesQuery.init(db=self.db, at=at, target_branch=target_branch, scope=scope)
        await delete_query.execute(db=self.db)
        orphan_candidate_ids = set(delete_query.get_touched_vertex_ids())
        touched_vertex_ids.update(orphan_candidate_ids)
        log.debug(
            f"Rollback delete phase complete ({len(orphan_candidate_ids)} vertices touched, "
            f"{time.monotonic() - started:.1f}s)"
        )

        started = time.monotonic()
        for id_batch in batched(orphan_candidate_ids, self.vertex_id_batch_size):
            orphan_query = await RollbackDeleteOrphanedVerticesQuery.init(db=self.db, vertex_ids=list(id_batch))
            await orphan_query.execute(db=self.db)
        log.debug(
            f"Rollback orphaned-vertex cleanup complete "
            f"({len(orphan_candidate_ids)} candidates, {time.monotonic() - started:.1f}s)"
        )

        if not restore_metadata:
            return

        started = time.monotonic()
        for id_batch in batched(touched_vertex_ids, self.vertex_id_batch_size):
            metadata_query = await RollbackRestoreMetadataQuery.init(
                db=self.db, vertex_ids=list(id_batch), at=at, scope=scope
            )
            await metadata_query.execute(db=self.db)
        log.debug(
            f"Rollback metadata restore complete "
            f"({len(touched_vertex_ids)} vertices checked, {time.monotonic() - started:.1f}s)"
        )
