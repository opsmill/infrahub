from __future__ import annotations

from typing import TYPE_CHECKING

from .write_blocker import MergeProtectionState

if TYPE_CHECKING:
    from infrahub.core.branch import Branch

    from .repository_import_guard import RepositoryImportGuard
    from .write_blocker import MergeWriteBlocker


class MergeStartGate:
    """Block writes for a merge only once the source branch passes the checks that need no graph write."""

    def __init__(self, merge_write_blocker: MergeWriteBlocker, repository_import_guard: RepositoryImportGuard) -> None:
        self.merge_write_blocker = merge_write_blocker
        self.repository_import_guard = repository_import_guard

    async def block_writes(self, branch: Branch) -> None:
        """Set the merge write block for `branch`, after checking its imports before and under the block.

        Raises:
            MergeRepositoryImportError: When an import on `branch` blocks the merge; the write block is not left set.

        """
        # Refusing before the block is set keeps a refused merge from rejecting the import it waits for.
        await self.repository_import_guard.verify(branch=branch)

        await self.merge_write_blocker.set(branch=branch.name, state=MergeProtectionState.MERGING)
        try:
            # An import can start or fail between the first check and the block.
            await self.repository_import_guard.verify(branch=branch)
        except BaseException:
            await self.merge_write_blocker.delete()
            raise
