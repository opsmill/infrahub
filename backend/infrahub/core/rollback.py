from __future__ import annotations

import time
from typing import TYPE_CHECKING

from infrahub.core.query.rollback import (
    RollbackDeleteEdgesQuery,
    RollbackReopenEdgesQuery,
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

    Reverses database changes in two passes:
    1. Reopen edges that were closed in the rollback window (reset `to`/`to_user_id` to NULL).
    2. Delete edges that were created in the rollback window, deleting any vertices the edge
       deletions orphaned in the same batch as their edges.

    Both passes cover the target branch and the global branch. On the target branch the window
    follows the scope and on the global branch it is always the exact timestamp. Any changes on
    the global branch with the exact timestamp were part of the change being rolled back, but
    other timestamps came from unrelated changes on other branches.

    Both passes restore the `previous_updated_at`/`previous_updated_by` metadata snapshots on the
    vertices the rolled-back writes had bumped.

    Idempotent, and resumable: every cleanup commits no later than the edge reversal it belongs
    to, so at any interruption point the not-yet-reversed edges still match a re-run and the
    already-done restores repeat as window-filtered no-ops. Nothing about the rollback's progress
    is kept outside the database.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def rollback(
        self,
        target_branch: Branch,
        at: Timestamp,
        scope: RollbackScope,
    ) -> None:
        started = time.monotonic()
        reopen_query = await RollbackReopenEdgesQuery.init(db=self.db, at=at, target_branch=target_branch, scope=scope)
        await reopen_query.execute(db=self.db)
        log.debug(f"Rollback reopen phase complete ({time.monotonic() - started:.1f}s)")

        started = time.monotonic()
        delete_query = await RollbackDeleteEdgesQuery.init(db=self.db, at=at, target_branch=target_branch, scope=scope)
        await delete_query.execute(db=self.db)
        log.debug(f"Rollback delete phase complete ({time.monotonic() - started:.1f}s)")
