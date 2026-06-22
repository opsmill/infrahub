from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.registry import registry
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.log import InfrahubLogger

    from .graph_merger import GraphMerger
    from .write_blocker import MergeWriteBlocker


class MergeRollbackHandler:
    """Best-effort in-process rollback of a failed merge.

    Returns True only when every sub-step succeeds and the branch is fully restored to OPEN. On any
    sub-step failure it returns False and deliberately leaves the write-protection key set (branch stays
    MERGING) so out-of-process recovery can take over rather than reopening a partially-recovered state.
    Never raises.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        graph_merger: GraphMerger,
        merge_write_blocker: MergeWriteBlocker,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.graph_merger = graph_merger
        self.merge_write_blocker = merge_write_blocker
        self.log = logger or get_logger()

    async def rollback(
        self,
        *,
        branch: Branch,
        at: Timestamp,
        pre_merge_schema: SchemaBranch,
        pre_merge_branched_from: str | None,
        user_id: str,
    ) -> bool:
        try:
            await self.graph_merger.rollback(at=at)
        except Exception:
            self.log.exception("Graph merge rollback failed during merge rollback")
            return False

        destination_branch = self.graph_merger.destination_branch
        try:
            # reset destination branch's schema
            registry.schema.set_schema_branch(name=destination_branch.name, schema=pre_merge_schema)
            destination_branch.update_schema_hash()
            await destination_branch.save(db=self.db, user_id=user_id)
        except Exception:
            # Hold the write protection (leave the branch MERGING + key set) rather than reopening on a
            # partially-recovered state, so the failure is handled by recovery instead of allowing writes.
            self.log.exception("Registry restore failed during merge rollback")
            return False

        try:
            # Lift the write protection BEFORE flipping the branch back to OPEN so that a failure
            # leaves the branch MERGING and it can be detected during recovery
            await self.merge_write_blocker.delete()

            branch.branched_from = pre_merge_branched_from
            branch.status = BranchStatus.OPEN
            await branch.save(db=self.db, user_id=user_id)
            registry.branch[branch.name] = branch
        except Exception:
            # Report a failed rollback rather than a clean one on a partially-restored state, so
            # recovery takes over. If the key delete failed, the branch is still MERGING with the key
            # set; if the delete succeeded but the OPEN flip did not, the branch is still durably
            # MERGING, which recovery still detects (its rollback is idempotent over already-reverted
            # data). Never raise: raising here would mask the original merge error that triggered the
            # rollback.
            self.log.exception("Branch state restore failed during merge rollback")
            return False

        self.log.info(f"Merge rollback completed; branch '{branch.name}' returned to OPEN")

        return True
