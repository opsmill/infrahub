"""Read a repository's commit log from a worker's existing clone.

The read itself never clones, fetches, pulls or takes the repository lock: it runs against git's
own consistent object store and must not queue behind an import. A worker holding no clone says so
and claims the single warm-up shared by all workers.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from git import BadName
from git.exc import GitCommandError

from infrahub.core.constants import InfrahubKind, RepositoryGitCondition, RepositoryGitUnavailableReason
from infrahub.exceptions import RepositoryError, RepositoryInvalidFileSystemError
from infrahub.git.base import InfrahubRepositoryBase
from infrahub.git.models import GitRepositoryWarmUp
from infrahub.log import get_logger
from infrahub.workflows.catalogue import GIT_REPOSITORY_WARM_UP

from .cache_keys import WARM_UP_TTL, warm_up_key
from .classification import classify, classify_commit
from .models import CommitEntry, CommitLogResult, GitStateFacts

if TYPE_CHECKING:
    from git import Repo
    from git.objects import Commit

    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.workflow import InfrahubWorkflow

    from .models import CommitLogRequest

log = get_logger()

NOT_CLONED_WARM_UP_STARTED_MESSAGE = (
    "The answering worker holds no local copy of this repository yet. A warm-up has been started."
)
NOT_CLONED_WARM_UP_PENDING_MESSAGE = (
    "The answering worker holds no local copy of this repository yet. A warm-up is already in progress."
)
NOT_CLONED_AWAITING_SYNC_MESSAGE = (
    "The answering worker holds no local copy of this repository yet. "
    "The repository's next sync creates it along with its first import."
)


class RepositoryLogReader:
    """Answer a repository's commit log for one Infrahub branch from the local clone."""

    def __init__(self, cache: InfrahubCache, workflow: InfrahubWorkflow, worker_identity: str) -> None:
        self._cache = cache
        self._workflow = workflow
        self._worker_identity = worker_identity

    async def commits(self, request: CommitLogRequest) -> CommitLogResult:
        """Return the paged log of ``request.git_ref``, newest first, with every commit classified.

        Raises:
            ValueError: When the repository kind has no commit log.
            RepositoryError: When a local copy exists but fails validation while no warm-up is in
                progress, or git fails while reading it.

        """
        repository = _build_repository(request=request)
        try:
            repo = await asyncio.to_thread(_open_clone, repository)
        except RepositoryInvalidFileSystemError:
            return await self._answer_not_cloned(request=request)
        except RepositoryError:
            # A clone in progress leaves a partial copy that fails validation the same way a broken one does.
            if await self._warm_up_in_progress(repository_id=request.repository_id):
                return _warm_up_pending()
            raise

        try:
            return await asyncio.to_thread(_read_commit_log, repo, request)
        except GitCommandError as exc:
            raise RepositoryError(
                identifier=request.repository_name,
                message=f"Git failed while reading the commit log of {request.repository_name}.",
            ) from exc
        finally:
            repo.close()

    async def _answer_not_cloned(self, request: CommitLogRequest) -> CommitLogResult:
        # The warm-up leaves a read-write repository with nothing imported to its sync, so none is started.
        if request.imported_commit is None and request.repository_kind == InfrahubKind.REPOSITORY:
            return CommitLogResult(
                condition=RepositoryGitCondition.UNAVAILABLE,
                unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
                error_message=NOT_CLONED_AWAITING_SYNC_MESSAGE,
            )

        key = warm_up_key(repository_id=request.repository_id)
        claimed = await self._cache.set(key=key, value=self._worker_identity, expires=WARM_UP_TTL, not_exists=True)
        if not claimed:
            return _warm_up_pending()

        try:
            warm_up = await self._workflow.submit_workflow(
                workflow=GIT_REPOSITORY_WARM_UP,
                parameters={
                    "model": GitRepositoryWarmUp(
                        repository_id=request.repository_id,
                        repository_name=request.repository_name,
                        repository_kind=request.repository_kind,
                        location=request.location,
                        infrahub_branch_name=request.infrahub_branch_name,
                    )
                },
            )
        except Exception:
            # Release the claim, or every worker reports a warm-up in progress that never started.
            await self._release_claim(key=key)
            raise

        return CommitLogResult(
            condition=RepositoryGitCondition.UNAVAILABLE,
            unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
            warm_up_task_id=str(warm_up.id),
            error_message=NOT_CLONED_WARM_UP_STARTED_MESSAGE,
        )

    async def _warm_up_in_progress(self, repository_id: str) -> bool:
        """Return whether a warm-up claim is held for the repository.

        Answers False when the cache cannot be read, so the validation error being handled is raised
        rather than replaced.
        """
        try:
            return await self._cache.get(key=warm_up_key(repository_id=repository_id)) is not None
        # Best-effort check inside an error path: the original error must reach the caller.
        except Exception:
            log.warning("Could not read the warm-up claim", repository_id=repository_id, exc_info=True)
            return False

    async def _release_claim(self, key: str) -> None:
        """Delete the warm-up claim, never letting a cache failure replace the error being handled.

        A claim left behind expires on its own, so failing to delete it only delays the next warm-up.
        """
        try:
            await self._cache.delete(key=key)
        # Best-effort cleanup inside an error path: the original error must reach the caller.
        except Exception:
            log.warning("Could not release the warm-up claim", key=key, exc_info=True)


def _warm_up_pending() -> CommitLogResult:
    return CommitLogResult(
        condition=RepositoryGitCondition.UNAVAILABLE,
        unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
        error_message=NOT_CLONED_WARM_UP_PENDING_MESSAGE,
    )


class _LocalCopy(InfrahubRepositoryBase):
    """A repository's on-disk copy, located and validated without reading its configuration from the graph.

    Only the directory layout and the main clone are used, so every branch-mapping and checkout
    behaviour raises rather than guessing at configuration it was never given.
    """

    async def resolve_checkout_ref(self) -> str:
        raise NotImplementedError(_READ_ONLY_COPY)

    def _get_mapped_remote_branch(self, branch_name: str) -> str:
        raise NotImplementedError(_READ_ONLY_COPY)

    def _get_mapped_target_branch(self, branch_name: str) -> str:
        raise NotImplementedError(_READ_ONLY_COPY)

    def _resolve_worktree_identifier(self, branch_name: str) -> str:
        raise NotImplementedError(_READ_ONLY_COPY)

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:
        raise NotImplementedError(_READ_ONLY_COPY)


_READ_ONLY_COPY = "A local copy opened to read its commit log is never mapped, checked out or updated"


def _build_repository(request: CommitLogRequest) -> _LocalCopy:
    match request.repository_kind:
        case InfrahubKind.REPOSITORY | InfrahubKind.READONLYREPOSITORY:
            return _LocalCopy.model_validate(
                {"id": request.repository_id, "name": request.repository_name, "location": request.location}
            )
        case unsupported_kind:
            raise ValueError(f"Reading a commit log is not supported for a {unsupported_kind}")


def _head_candidates(git_ref: str, is_read_only: bool) -> tuple[str, ...]:
    """Return the revisions naming the remote head, in the order they are tried.

    A read-only repository may track a tag. A bare name is never tried, because it would also
    match the local branch the clone checked out and keep reporting a ref the remote deleted.
    """
    if is_read_only:
        return (f"origin/{git_ref}", f"refs/tags/{git_ref}")
    return (f"origin/{git_ref}",)


def _open_clone(repository: InfrahubRepositoryBase) -> Repo:
    repository.validate_local_directories()
    return repository.get_git_repo_main()


def _resolve_commit(repo: Repo, revisions: tuple[str, ...]) -> Commit | None:
    """Return the first revision naming a commit the clone holds."""
    for revision in revisions:
        try:
            return repo.commit(revision)
        # An unknown name raises BadName and an unknown full hash raises ValueError.
        except (BadName, ValueError):
            continue
    return None


def _resolve_head(repo: Repo, git_ref: str, is_read_only: bool) -> Commit | None:
    """Return the commit the remote branch or tracked ref points at, as last fetched.

    A read-only repository may also be pinned to a commit hash. A bare ref is only accepted as
    that, never as a name, since a bare name also matches a local branch the remote has deleted.
    """
    head = _resolve_commit(repo=repo, revisions=_head_candidates(git_ref=git_ref, is_read_only=is_read_only))
    if head is not None or not is_read_only:
        return head

    pinned = _resolve_commit(repo=repo, revisions=(git_ref,))
    if pinned is not None and pinned.hexsha.startswith(git_ref.lower()):
        return pinned
    return None


def _read_fetched_at(repo: Repo) -> datetime | None:
    try:
        modified = (Path(repo.git_dir) / "FETCH_HEAD").stat().st_mtime
    # An unreadable file means no known fetch time, and its error would carry the clone's path.
    except OSError:
        return None
    return datetime.fromtimestamp(modified, tz=UTC)


def _measure_facts(
    repo: Repo, head: Commit | None, imported_commit: str | None, imported: Commit | None, is_read_only: bool
) -> GitStateFacts:
    """Measure the ancestry of the imported commit only once the clone has resolved it.

    An ancestry test against an unresolvable hash raises rather than answering.
    """
    return GitStateFacts(
        head=head.hexsha if head is not None else None,
        imported=imported.hexsha if imported is not None else imported_commit,
        imported_resolvable=None if imported_commit is None else imported is not None,
        imported_is_ancestor_of_head=(
            repo.is_ancestor(ancestor_rev=imported, rev=head) if imported is not None and head is not None else None
        ),
        ref_is_configured=is_read_only,
    )


def _to_entry(
    commit: Commit, facts: GitStateFacts, condition: RepositoryGitCondition, pending: frozenset[str]
) -> CommitEntry:
    return CommitEntry(
        hash=commit.hexsha,
        message=str(commit.message),
        author_name=commit.author.name or "",
        authored_at=commit.authored_datetime,
        committed_at=commit.committed_datetime,
        state=classify_commit(
            hash=commit.hexsha, is_pending=commit.hexsha in pending, facts=facts, condition=condition
        ),
    )


def _read_commit_log(repo: Repo, request: CommitLogRequest) -> CommitLogResult:
    is_read_only = request.repository_kind == InfrahubKind.READONLYREPOSITORY
    head = _resolve_head(repo=repo, git_ref=request.git_ref, is_read_only=is_read_only)
    imported = (
        _resolve_commit(repo=repo, revisions=(request.imported_commit,))
        if request.imported_commit is not None
        else None
    )
    facts = _measure_facts(
        repo=repo, head=head, imported_commit=request.imported_commit, imported=imported, is_read_only=is_read_only
    )
    condition = classify(facts=facts)

    # One walk of the range not yet imported places every listed commit and counts the range.
    pending: frozenset[str] = frozenset()
    pending_count: int | None = None
    if condition is RepositoryGitCondition.BEHIND and head is not None and imported is not None:
        pending = frozenset(repo.git.rev_list(f"{imported.hexsha}..{head.hexsha}").split())
        if request.include_pending_count:
            pending_count = len(pending)

    # With the tracked ref gone, the history Infrahub still runs is listed from the imported commit.
    start = imported if condition is RepositoryGitCondition.REF_MISSING else head
    commits: tuple[CommitEntry, ...] = ()
    if start is not None:
        commits = tuple(
            _to_entry(commit=commit, facts=facts, condition=condition, pending=pending)
            for commit in repo.iter_commits(start, max_count=request.limit, skip=request.offset)
        )

    return CommitLogResult(
        condition=condition,
        remote_head=facts.head,
        imported_commit=facts.imported if facts.imported_resolvable else None,
        pending_count=pending_count,
        commits=commits,
        fetched_at=_read_fetched_at(repo=repo),
    )
