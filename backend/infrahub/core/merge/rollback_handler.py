from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.registry import registry
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.merger.merger import DiffMerger
    from infrahub.core.models import SchemaBranchHash
    from infrahub.core.schema.manager import SchemaManager
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.log import InfrahubLogger

    from .write_blocker import MergeWriteBlocker


@dataclass(frozen=True)
class PreMergeState:
    """In-memory state captured right before a merge writes anything, to be restored on rollback."""

    destination_schema: SchemaBranch
    destination_schema_changed_at: str | None
    destination_schema_hash: SchemaBranchHash | None
    source_branched_from: str | None


class MergeRollbackHandler:
    """Best-effort in-process rollback of a failed merge.

    The graph revert is the same range rollback out-of-process recovery uses, keyed on the merge
    start; on top of it this handler restores the in-memory state (schema registry, branch objects,
    write protection) that out-of-process recovery gets for free by reloading from the database.

    Returns True only when every sub-step succeeds and the branch is fully restored to OPEN. On any
    sub-step failure it returns False and leaves the partially-recovered state for out-of-process
    recovery (or an operator) to reconcile. Never raises.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_merger: DiffMerger,
        merge_write_blocker: MergeWriteBlocker,
        schema_manager: SchemaManager,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.diff_merger = diff_merger
        self.merge_write_blocker = merge_write_blocker
        self.schema_manager = schema_manager
        self.log = logger or get_logger()

    async def rollback(
        self,
        *,
        merge_started_at: Timestamp,
        pre_merge_state: PreMergeState,
        user_id: str,
    ) -> bool:
        try:
            await self.diff_merger.rollback(merge_started_at=merge_started_at)
        except Exception:
            self.log.exception("Graph rollback failed during merge rollback")
            return False

        try:
            # Reset the destination branch's schema. The hash and changed-at are restored literally
            # rather than recomputed, which would stamp schema_changed_at with the rollback time.
            self.schema_manager.set_schema_branch(
                name=self.destination_branch.name, schema=pre_merge_state.destination_schema
            )
            self.destination_branch.schema_hash = pre_merge_state.destination_schema_hash
            self.destination_branch.schema_changed_at = pre_merge_state.destination_schema_changed_at
            await self.destination_branch.save(db=self.db, user_id=user_id)
            registry.branch[self.destination_branch.name] = self.destination_branch
        except Exception:
            # Hold the write protection (leave the branch MERGING + key set) rather than reopening on a
            # partially-recovered state, so the failure is handled by recovery instead of allowing writes.
            self.log.exception("Registry restore failed during merge rollback")
            return False

        try:
            # Lift the write protection BEFORE flipping the branch back to OPEN so that a failure
            # leaves the branch MERGING and it can be detected during recovery
            await self.merge_write_blocker.delete()

            self.source_branch.branched_from = pre_merge_state.source_branched_from
            self.source_branch.status = BranchStatus.OPEN
            await self.source_branch.save(db=self.db, user_id=user_id)
            registry.branch[self.source_branch.name] = self.source_branch
        except Exception:
            # Never raise: raising here would mask the original merge error that triggered the rollback.
            self.log.exception("Branch state restore failed during merge rollback")
            return False

        self.log.info(f"Merge rollback completed; branch '{self.source_branch.name}' returned to OPEN")

        return True
