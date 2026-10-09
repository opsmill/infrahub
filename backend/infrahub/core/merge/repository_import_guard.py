from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.exceptions import MergeRepositoryImportError
from infrahub.git.sync_status import BranchImportVerdict

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.git.sync_status import RepositoryBranchSyncStatusReader


class RepositoryImportGuard:
    """Refuse to merge a branch on which a repository's objects may not match the content of the branch."""

    def __init__(self, status_reader: RepositoryBranchSyncStatusReader) -> None:
        self.status_reader = status_reader

    async def verify(self, branch: Branch) -> None:
        """Raise when an import on `branch` failed or has not completed.

        Raises:
            MergeRepositoryImportError: When at least one repository's import blocks the merge.

        """
        statuses = await self.status_reader.list_statuses_on_branch(branch=branch)
        failed = sorted(status.repository_name for status in statuses if status.verdict == BranchImportVerdict.FAILED)
        incomplete = sorted(
            status.repository_name for status in statuses if status.verdict == BranchImportVerdict.INCOMPLETE
        )
        if failed or incomplete:
            raise MergeRepositoryImportError(failed_repositories=failed, incomplete_repositories=incomplete)
