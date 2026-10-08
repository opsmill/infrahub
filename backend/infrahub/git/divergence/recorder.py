from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from infrahub.git.divergence.models import RefClassification, RewriteRecord

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.git.divergence.models import RefDivergence
    from infrahub.git.divergence.protocols import RepositoryRecordStore


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


class HistoryRewriteRecorder:
    """Records the last history rewrite of a branch on its repository, and counts the rewrites.

    The classification alone decides whether to record, so a re-target writes nothing and this
    never reads the cache.
    """

    def __init__(self, store: RepositoryRecordStore, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self.store = store
        self.clock = clock

    async def record(self, repository_id: str, divergence: RefDivergence) -> None:
        """Write the rewrite record on the branch the divergence names, when it names a rewrite.

        The record replaces the previous one. Its count adds one to the count the branch reads,
        which includes the count of the branch it was created from.

        Raises:
            RepositoryError: When the store cannot read the count or write the record.

        """
        # A rewrite always carries both commits, so the last two checks only narrow their types.
        if (
            divergence.classification is not RefClassification.REWRITE
            or divergence.imported_commit is None
            or divergence.remote_head is None
        ):
            return

        previous_commit = divergence.imported_commit
        commit = divergence.remote_head
        await self.store.write_record(
            repository_id=repository_id,
            infrahub_branch_name=divergence.infrahub_branch_name,
            build_record=lambda current_count: RewriteRecord(
                previous_commit=previous_commit,
                commit=commit,
                rewritten_at=self.clock(),
                rewrite_count=(current_count or 0) + 1,
            ),
        )
