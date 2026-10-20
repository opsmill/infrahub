from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreRepository
from infrahub.core.timestamp import Timestamp
from infrahub.git.commit_id import readable_commit
from infrahub.git.writeback.models import PendingMerge
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

log = get_logger()


@dataclass(frozen=True)
class _Trunk:
    """What the default branch records for a repository."""

    repository_name: str
    git_branch: str
    """The remote branch that a delivery pushes to."""
    commit: str | None


async def read_pending_merges(
    *, db: InfrahubDatabase, source_branch: Branch, default_branch: Branch, repository_ids: Collection[str]
) -> dict[str, PendingMerge]:
    """Return a new queue entry, by repository id, for each repository whose content the merge of the branch changes.

    The merge changes no content of a repository when the branch holds no commit for it, or when the branch holds
    the commit that the default branch held when the branch was created or last rebased, or the commit that
    it holds now.
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
    trunks = await _read_trunks(db=db, default_branch=default_branch, repository_ids=repository_ids)
    merged_at = datetime.now(UTC)
    pending: dict[str, PendingMerge] = {}
    for repository_id, commit in source.items():
        trunk = trunks.get(repository_id)
        if commit in {forked.get(repository_id), trunk.commit if trunk else None}:
            continue
        if trunk is not None and _comes_from_the_trunk(source_branch_name=source_branch.name, trunk=trunk):
            continue
        pending[repository_id] = _new_pending_merge(
            source_branch_name=source_branch.name, source_commit=commit, merged_at=merged_at
        )
    return pending


async def read_pending_merge_of_commit(
    *, db: InfrahubDatabase, source_branch_name: str, source_commit: str, default_branch: Branch, repository_id: str
) -> PendingMerge | None:
    """Return a new queue entry for a source commit whose branch is gone, or None when the default branch records it.

    The commit that the default branch held at the fork of a deleted branch is unknown, so only the commit recorded
    now can show that the merge changes no content.
    """
    trunk = (await _read_trunks(db=db, default_branch=default_branch, repository_ids=[repository_id])).get(
        repository_id
    )
    if trunk is not None and (
        trunk.commit == source_commit or _comes_from_the_trunk(source_branch_name=source_branch_name, trunk=trunk)
    ):
        return None
    return _new_pending_merge(
        source_branch_name=source_branch_name, source_commit=source_commit, merged_at=datetime.now(UTC)
    )


def _new_pending_merge(*, source_branch_name: str, source_commit: str, merged_at: datetime) -> PendingMerge:
    return PendingMerge(
        entry_id=str(uuid4()),
        source_branch=source_branch_name,
        # Only the default branch maps to a remote branch of another name, and a merge never comes from it.
        source_git_branch=source_branch_name,
        source_commit=source_commit,
        merged_at=merged_at,
    )


def _comes_from_the_trunk(*, source_branch_name: str, trunk: _Trunk) -> bool:
    """Return whether the merge comes from the remote branch that a delivery pushes to, and log it when it does."""
    if source_branch_name != trunk.git_branch:
        return False
    # The queue refuses such a merge, and a refusal would cost the whole retry chain under the global merge lock.
    log.warning(
        f"Skipped the merge of branch {source_branch_name} for repository {trunk.repository_name}: the remote branch "
        f"{source_branch_name} is the one that a delivery pushes to, so there is nothing to push."
    )
    return True


async def _read_trunks(
    *, db: InfrahubDatabase, default_branch: Branch, repository_ids: Collection[str]
) -> dict[str, _Trunk]:
    repositories = await NodeManager.query(
        schema=CoreRepository,
        db=db,
        branch=default_branch,
        filters={"ids": list(repository_ids)},
        fields={"name": None, "default_branch": None, "commit": None},
    )
    return {
        repository.id: _Trunk(
            repository_name=repository.name.value,
            git_branch=repository.default_branch.value,
            commit=_readable_commit_of(repository=repository, branch=default_branch),
        )
        for repository in repositories
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
    commits: dict[str, str] = {}
    for repository in repositories:
        commit = _readable_commit_of(repository=repository, branch=branch)
        if commit is not None:
            commits[repository.id] = commit
    return commits


def _readable_commit_of(*, repository: CoreRepository, branch: Branch) -> str | None:
    value = repository.commit.value
    commit = readable_commit(value)
    if commit is None and value:
        # The API stores any text as the commit, and one bad value must not stop the merge of other repositories.
        log.warning(
            f"Ignored the commit {value!r} of repository {repository.id} on branch {branch.name}, because it is "
            "not a full commit id."
        )
    return commit
