from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, cast

from infrahub.exceptions import ResourceNotFoundError
from infrahub.git.repository import get_initialized_repo
from infrahub.message_bus.types import KVTTL
from infrahub.workers.dependencies import get_cache

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.message_bus.types import ProposedChangeRepository
    from infrahub.services.adapters.cache import InfrahubCache

SCHEMA_CHANGE = re.compile(r"^Schema[A-Z]")


@dataclass(frozen=True, kw_only=True, slots=True)
class RepositoryFileDiff:
    """File-level diff for a single repository between two commits."""

    files_changed: list[str] = field(default_factory=list)
    files_added: list[str] = field(default_factory=list)
    files_removed: list[str] = field(default_factory=list)


class RepositoryFileDiffer(Protocol):
    """Computes the file diff for a repository between two commits.

    Implementations resolve the worktree for the given repository kind and return the files that
    differ between the source and destination commits.
    """

    async def calculate_diff(
        self,
        *,
        repository_id: str,
        repository_name: str,
        repository_kind: str,
        source_commit: str,
        destination_commit: str,
    ) -> RepositoryFileDiff: ...


class GitRepositoryFileDiffer:
    """RepositoryFileDiffer backed by the on-disk git worktree.

    The repository kind selects which repository class loads the worktree; the two commits are the
    tracked Git branch tips for a managed repository or the per-branch pinned commits for a
    read-only repository, already resolved per Infrahub branch by the gather queries.
    """

    def __init__(self, client: InfrahubClient) -> None:
        self._client = client

    async def calculate_diff(
        self,
        *,
        repository_id: str,
        repository_name: str,
        repository_kind: str,
        source_commit: str,
        destination_commit: str,
    ) -> RepositoryFileDiff:
        git_repo = await get_initialized_repo(
            client=self._client,
            repository_id=repository_id,
            name=repository_name,
            repository_kind=repository_kind,
        )
        files_changed, files_added, files_removed = await git_repo.calculate_diff_between_commits(
            first_commit=destination_commit, second_commit=source_commit
        )
        return RepositoryFileDiff(files_changed=files_changed, files_added=files_added, files_removed=files_removed)


class RepositoryFileDiffPopulator:
    """Populates the per-repository file diff on a set of proposed-change repositories."""

    def __init__(self, differ: RepositoryFileDiffer) -> None:
        self._differ = differ

    async def populate(self, repositories: list[ProposedChangeRepository]) -> None:
        """Populate files_added/changed/removed for every linked repository with a non-empty commit diff.

        The diff is computed per repository and per branch pair for both managed and read-only
        repositories, independent of the source branch's sync_with_git flag. A repository whose source
        and destination commits match has no file changes and is left untouched.
        """
        for repo in repositories:
            if not repo.has_file_diff:
                continue
            diff = await self._differ.calculate_diff(
                repository_id=repo.repository_id,
                repository_name=repo.repository_name,
                repository_kind=repo.kind,
                source_commit=repo.source_commit,
                destination_commit=repo.destination_commit,
            )
            repo.files_changed = diff.files_changed
            repo.files_added = diff.files_added
            repo.files_removed = diff.files_removed


def has_data_changes(diff_summary: list[NodeDiff], branch: str) -> bool:
    """Indicates if there are node or schema changes within the branch."""
    return any(entry["branch"] == branch for entry in diff_summary)


def has_node_changes(diff_summary: list[NodeDiff], branch: str) -> bool:
    """Indicates if there is at least one node object that has been modified in the branch."""
    return any(entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"]) for entry in diff_summary)


def get_modified_kinds(diff_summary: list[NodeDiff], branch: str) -> list[str]:
    """Return a list of non schema kinds that have been modified on the branch."""
    return list(
        {
            entry["kind"]
            for entry in diff_summary
            if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
        }
    )


async def set_diff_summary_cache(pipeline_id: UUID, diff_summary: list[NodeDiff], cache: InfrahubCache) -> None:
    serialized = json.dumps(diff_summary)
    await cache.set(
        key=f"proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_summary",
        value=serialized,
        expires=KVTTL.TWO_HOURS,
    )


async def get_diff_summary_cache(pipeline_id: UUID) -> list[NodeDiff]:
    cache = await get_cache()
    summary_payload = await cache.get(
        key=f"proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_summary",
    )

    if not summary_payload:
        raise ResourceNotFoundError(message=f"Diff summary for pipeline {pipeline_id} was not found in the cache")

    return cast("list[NodeDiff]", json.loads(summary_payload))
