"""Read a repository's commit log and branch heads from a worker's existing clone.

The read itself never clones, fetches, pulls or takes the repository lock: it runs against git's
own consistent object store and must not queue behind an import. A worker holding no clone says so
and claims the single warm-up shared by all workers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from git import BadName
from git.exc import GitCommandError
from git.objects import Commit, Object
from git.refs import Reference, TagReference

from infrahub.core.constants import InfrahubKind, RepositoryGitCondition, RepositoryGitUnavailableReason
from infrahub.exceptions import RepositoryError, RepositoryInvalidFileSystemError
from infrahub.git.base import InfrahubRepositoryBase
from infrahub.git.models import GitRepositoryWarmUp
from infrahub.log import get_logger
from infrahub.workflows.catalogue import GIT_REPOSITORY_WARM_UP

from .cache_keys import WARM_UP_TTL, warm_up_key
from .classification import classify, classify_commit
from .models import BranchDriftResult, BranchDriftRow, CommitEntry, CommitLogResult, GitStateFacts

if TYPE_CHECKING:
    from collections.abc import Callable

    from git import Repo

    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.workflow import InfrahubWorkflow

    from .models import BranchHeadsRequest, BranchRef, CommitLogRequest

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


@dataclass(frozen=True)
class _NotCloned:
    """Why the answering worker could not read its clone, and the warm-up it started if any."""

    error_message: str
    warm_up_task_id: str | None = None


_WARM_UP_PENDING = _NotCloned(error_message=NOT_CLONED_WARM_UP_PENDING_MESSAGE)


class RepositoryLogReader:
    """Answer a repository's commit log for one Infrahub branch, or the remote head of every branch, from the local clone."""

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
        repository = _build_repository(
            repository_id=request.repository_id,
            repository_name=request.repository_name,
            repository_kind=request.repository_kind,
            location=request.location,
            subject="a commit log",
        )
        opened = await self._open_clone(
            repository=repository,
            warm_up=GitRepositoryWarmUp(
                repository_id=request.repository_id,
                repository_name=request.repository_name,
                repository_kind=request.repository_kind,
                location=request.location,
                infrahub_branch_name=request.infrahub_branch_name,
            ),
            has_imported_commit=request.imported_commit is not None,
        )
        if isinstance(opened, _NotCloned):
            return CommitLogResult(
                condition=RepositoryGitCondition.UNAVAILABLE,
                unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
                warm_up_task_id=opened.warm_up_task_id,
                error_message=opened.error_message,
            )

        return await _read_and_close(
            repo=opened,
            repository_name=request.repository_name,
            subject="the commit log",
            read=lambda: _read_commit_log(repo=opened, request=request),
        )

    async def branch_heads(self, request: BranchHeadsRequest) -> BranchDriftResult:
        """Return every requested branch with its remote head and condition, reading only the refs the request names.

        Raises:
            ValueError: When the repository kind has no branch heads.
            RepositoryError: When a local copy exists but fails validation while no warm-up is in
                progress, or git fails while reading it.

        """
        repository = _build_repository(
            repository_id=request.repository_id,
            repository_name=request.repository_name,
            repository_kind=request.repository_kind,
            location=request.location,
            subject="branch heads",
        )
        if not request.branches:
            return BranchDriftResult()

        # Any branch with something imported gives the warm-up a commit to pin every worker to.
        warm_up_branch = next(
            (branch for branch in request.branches if branch.tracked_commit is not None), request.branches[0]
        )
        opened = await self._open_clone(
            repository=repository,
            warm_up=GitRepositoryWarmUp(
                repository_id=request.repository_id,
                repository_name=request.repository_name,
                repository_kind=request.repository_kind,
                location=request.location,
                infrahub_branch_name=warm_up_branch.branch_name,
            ),
            has_imported_commit=warm_up_branch.tracked_commit is not None,
        )
        if isinstance(opened, _NotCloned):
            return BranchDriftResult(
                unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
                warm_up_task_id=opened.warm_up_task_id,
                error_message=opened.error_message,
            )

        return await _read_and_close(
            repo=opened,
            repository_name=request.repository_name,
            subject="the branch heads",
            read=lambda: _read_branch_heads(repo=opened, request=request),
        )

    async def _open_clone(
        self, repository: InfrahubRepositoryBase, warm_up: GitRepositoryWarmUp, has_imported_commit: bool
    ) -> Repo | _NotCloned:
        """Open the validated main clone, or report it missing and claim the warm-up that creates it.

        Raises:
            RepositoryError: When a local copy exists but fails validation while no warm-up is in progress.

        """
        try:
            return await asyncio.to_thread(_open_validated_clone, repository)
        except RepositoryInvalidFileSystemError:
            return await self._answer_not_cloned(warm_up=warm_up, has_imported_commit=has_imported_commit)
        except RepositoryError:
            # A clone in progress leaves a partial copy that fails validation the same way a broken one does.
            if await self._warm_up_in_progress(repository_id=warm_up.repository_id):
                return _WARM_UP_PENDING
            raise

    async def _answer_not_cloned(self, warm_up: GitRepositoryWarmUp, has_imported_commit: bool) -> _NotCloned:
        # The warm-up leaves a read-write repository with nothing imported to its sync, so none is started.
        if not has_imported_commit and warm_up.repository_kind == InfrahubKind.REPOSITORY:
            return _NotCloned(error_message=NOT_CLONED_AWAITING_SYNC_MESSAGE)

        key = warm_up_key(repository_id=warm_up.repository_id)
        claimed = await self._cache.set(key=key, value=self._worker_identity, expires=WARM_UP_TTL, not_exists=True)
        if not claimed:
            return _WARM_UP_PENDING

        try:
            run = await self._workflow.submit_workflow(workflow=GIT_REPOSITORY_WARM_UP, parameters={"model": warm_up})
        except Exception:
            # Release the claim, or every worker reports a warm-up in progress that never started.
            await self._release_claim(key=key)
            raise

        return _NotCloned(error_message=NOT_CLONED_WARM_UP_STARTED_MESSAGE, warm_up_task_id=str(run.id))

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


async def _read_and_close[ReadResult](
    repo: Repo, repository_name: str, subject: str, read: Callable[[], ReadResult]
) -> ReadResult:
    """Run a blocking read of the clone off the event loop, closing the clone once it ends.

    Raises:
        RepositoryError: When git fails, with a message that carries no path or git output.

    """
    try:
        return await asyncio.to_thread(read)
    except GitCommandError as exc:
        raise RepositoryError(
            identifier=repository_name, message=f"Git failed while reading {subject} of {repository_name}."
        ) from exc
    finally:
        repo.close()


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


_READ_ONLY_COPY = "A local copy opened to read its commit log or branch heads is never mapped, checked out or updated"


def _build_repository(
    repository_id: str, repository_name: str, repository_kind: str, location: str, subject: str
) -> _LocalCopy:
    match repository_kind:
        case InfrahubKind.REPOSITORY | InfrahubKind.READONLYREPOSITORY:
            return _LocalCopy.model_validate({"id": repository_id, "name": repository_name, "location": location})
        case unsupported_kind:
            raise ValueError(f"Reading {subject} is not supported for a {unsupported_kind}")


def _head_candidates(git_ref: str, is_read_only: bool) -> tuple[str, ...]:
    """Return the revisions naming the remote head, in the order they are tried.

    A read-only repository may track a tag. A bare name is never tried, because it would also
    match the local branch the clone checked out and keep reporting a ref the remote deleted.
    """
    if is_read_only:
        return (f"origin/{git_ref}", f"refs/tags/{git_ref}")
    return (f"origin/{git_ref}",)


def _open_validated_clone(repository: InfrahubRepositoryBase) -> Repo:
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
    return _resolve_pinned_commit(repo=repo, git_ref=git_ref)


def _resolve_pinned_commit(repo: Repo, git_ref: str) -> Commit | None:
    """Return the commit a read-only ref names when the ref is a commit hash, never when it is a name."""
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
    head: str | None,
    imported_commit: str | None,
    imported: str | None,
    is_read_only: bool,
    is_ancestor: Callable[[str, str], bool],
) -> GitStateFacts:
    """Measure the ancestry of the imported commit only once the clone has resolved it.

    An ancestry test against an unresolvable hash raises rather than answering, and a head equal to
    the imported commit is in sync without one.
    """
    return GitStateFacts(
        head=head,
        imported=imported if imported is not None else imported_commit,
        imported_resolvable=None if imported_commit is None else imported is not None,
        imported_is_ancestor_of_head=(
            is_ancestor(imported, head) if imported is not None and head is not None and head != imported else None
        ),
        ref_is_configured=is_read_only,
    )


def _is_ancestor_in(repo: Repo) -> Callable[[str, str], bool]:
    def is_ancestor(ancestor: str, descendant: str) -> bool:
        # A commit built from its full hash costs no object lookup, unlike one resolved by name.
        return repo.is_ancestor(
            ancestor_rev=Commit(repo=repo, binsha=bytes.fromhex(ancestor)),
            rev=Commit(repo=repo, binsha=bytes.fromhex(descendant)),
        )

    return is_ancestor


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
            commit_hash=commit.hexsha, is_pending=commit.hexsha in pending, facts=facts, condition=condition
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
        head=head.hexsha if head is not None else None,
        imported_commit=request.imported_commit,
        imported=imported.hexsha if imported is not None else None,
        is_read_only=is_read_only,
        is_ancestor=_is_ancestor_in(repo=repo),
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


def _read_tag_head(repo: Repo, git_ref: str) -> str | None:
    try:
        commit = TagReference(repo=repo, path=f"refs/tags/{git_ref}").commit
        # An annotated tag names its target without the clone necessarily holding it.
        repo.odb.info(commit.binsha)
    # An absent or malformed tag, or one at a tree, a blob or an object the clone does not hold, tracks nothing.
    except ValueError:
        return None
    return commit.hexsha


def _read_remote_head(repo: Repo, git_ref: str, repository_name: str) -> str | None:
    # The remote's HEAD points at its default branch and is never a branch of its own.
    if git_ref == "HEAD":
        return None
    path = f"refs/remotes/origin/{git_ref}"
    try:
        hexsha = Reference.dereference_recursive(repo=repo, ref_path=path)
    # An absent or malformed ref name means the remote has no such branch.
    except ValueError:
        return None
    try:
        target = Object.new_from_sha(repo=repo, sha1=bytes.fromhex(hexsha))
    # A remote ref at an object the clone does not hold must not fail every other branch.
    except ValueError:
        target = None
    if isinstance(target, Commit):
        return target.hexsha
    log.warning(
        "Skipping a remote ref that names no commit the clone holds", repository_name=repository_name, ref=git_ref
    )
    return None


def _read_branch_heads(repo: Repo, request: BranchHeadsRequest) -> BranchDriftResult:
    is_read_only = request.repository_kind == InfrahubKind.READONLYREPOSITORY

    # Many branches share a tracked commit and a remote head, so each lookup is made once per pass.
    @cache
    def resolve_imported(commit: str) -> str | None:
        resolved = _resolve_commit(repo=repo, revisions=(commit,))
        return resolved.hexsha if resolved is not None else None

    is_ancestor = cache(_is_ancestor_in(repo=repo))

    @cache
    def head_of(git_ref: str) -> str | None:
        head = _read_remote_head(repo=repo, git_ref=git_ref, repository_name=request.repository_name)
        if head is not None or not is_read_only:
            return head
        head = _read_tag_head(repo=repo, git_ref=git_ref)
        if head is not None:
            return head
        pinned = _resolve_pinned_commit(repo=repo, git_ref=git_ref)
        return pinned.hexsha if pinned is not None else None

    return BranchDriftResult(
        branches=tuple(
            _drift_row(
                branch=branch,
                facts=_measure_facts(
                    head=head_of(branch.git_ref),
                    imported_commit=branch.tracked_commit,
                    imported=resolve_imported(branch.tracked_commit) if branch.tracked_commit is not None else None,
                    is_read_only=is_read_only,
                    is_ancestor=is_ancestor,
                ),
            )
            for branch in request.branches
        ),
        fetched_at=_read_fetched_at(repo=repo),
    )


def _drift_row(branch: BranchRef, facts: GitStateFacts) -> BranchDriftRow:
    return BranchDriftRow(
        branch_name=branch.branch_name,
        git_ref=branch.git_ref,
        tracked_commit=branch.tracked_commit,
        remote_head=facts.head,
        condition=classify(facts=facts),
    )
