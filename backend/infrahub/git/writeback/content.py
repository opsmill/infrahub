from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreRepository
from infrahub.core.timestamp import Timestamp
from infrahub.git.writeback.models import PendingMerge

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def read_pending_merges(
    *, db: InfrahubDatabase, source_branch: Branch, default_branch: Branch, repository_ids: Collection[str]
) -> dict[str, PendingMerge]:
    """Return a new queue entry, by repository id, for each repository whose content the merge of the branch changes.

    The merge changes no content of a repository when the branch holds no commit for it, or when the branch holds
    the commit that the default branch held when the branch was created, or the commit that it holds now.
    """
    if not repository_ids:
        return {}
    source = await _read_commits(db=db, branch=source_branch, repository_ids=repository_ids, at=None)
    forked = await _read_commits(
        db=db,
        branch=default_branch,
        repository_ids=repository_ids,
        at=Timestamp(source_branch.get_branched_from()),
    )
    recorded = await _read_commits(db=db, branch=default_branch, repository_ids=repository_ids, at=None)
    merged_at = datetime.now(UTC)
    return {
        repository_id: PendingMerge(
            entry_id=str(uuid4()),
            source_branch=source_branch.name,
            # Only the default branch maps to a remote branch of another name, and a merge never comes from it.
            source_git_branch=source_branch.name,
            source_commit=commit,
            merged_at=merged_at,
        )
        for repository_id, commit in source.items()
        if commit not in {forked.get(repository_id), recorded.get(repository_id)}
    }


async def _read_commits(
    *, db: InfrahubDatabase, branch: Branch, repository_ids: Collection[str], at: Timestamp | None
) -> dict[str, str]:
    repositories = await NodeManager.query(
        schema=CoreRepository,
        db=db,
        branch=branch,
        at=at,
        filters={"ids": list(repository_ids)},
        fields={"commit": None},
    )
    return {repository.id: repository.commit.value for repository in repositories if repository.commit.value}
