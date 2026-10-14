from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from git import Repo
from git.exc import GitCommandError
from infrahub_sdk.protocols import CoreRepository

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import RepositoryError
from infrahub.git.commit_id import readable_commit
from infrahub.git.divergence.gateway import GitAncestryGateway
from infrahub.git.writeback.constants import FETCH_TIMEOUT_SECONDS, PUSH_TIMEOUT_SECONDS
from infrahub.git.writeback.ports import ReplayResult
from infrahub.log import get_run_logger
from infrahub.message_bus import Meta, messages

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from infrahub.git.repository import InfrahubRepository
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

log = get_run_logger()

MERGE_MESSAGE = "Merged by Infrahub"

KILLED_COMMAND_TEXT = "Timeout: the command "
"""How GitPython 3.1 starts the error text of a command that it stopped at ``kill_after_timeout``."""

MISSING_REMOTE_BRANCH_TEXT = "remote ref does not exist"
"""What Git reports when a push deletes a branch that the remote does not have."""

UNKNOWN_REF_STATUS = 1
"""What `git rev-parse --verify --quiet` returns for a ref that does not exist."""


class RepositoryDeliveryGitAdapter:
    """The Git work of a delivery on one repository and its destination worktree, which implements `DeliveryGitPort`.

    The caller holds the lock of the repository, so no other Git process on this worker writes to the clone.
    """

    def __init__(
        self,
        *,
        repository: InfrahubRepository,
        destination_branch: str,
        destination_branch_id: str,
        message_bus: InfrahubMessageBus,
        initiator_id: str,
        request_id: str,
        use_explicit_merge_commit: bool,
        local_timeout_seconds: float,
    ) -> None:
        """Bind the adapter to the Infrahub branch that receives the merges.

        Args:
            initiator_id: The worker identity that the messages to the other workers carry.
            request_id: The request id that the messages to the other workers carry.
            local_timeout_seconds: The time bound of each Git command that does not reach the remote.

        """
        self.repository = repository
        self.destination_branch = destination_branch
        self.destination_branch_id = destination_branch_id
        self.message_bus = message_bus
        self.initiator_id = initiator_id
        self.request_id = request_id
        self.use_explicit_merge_commit = use_explicit_merge_commit
        self.local_timeout_seconds = local_timeout_seconds

    async def fetch(self) -> None:
        """Fetch from the remote.

        Raises:
            RepositoryError: The clone has no `origin` remote.

        """
        if not await self.repository.fetch(timeout_seconds=FETCH_TIMEOUT_SECONDS):
            raise self._no_origin()

    def remote_head(self, *, git_branch: str) -> str | None:
        repo = self.repository.get_git_repo_main()
        with self._bounded():
            try:
                # The object database of GitPython reads through a process that no time bound covers.
                return str(
                    repo.git.rev_parse(
                        "--verify",
                        "--quiet",
                        f"refs/remotes/origin/{git_branch}",
                        kill_after_timeout=self.local_timeout_seconds,
                    )
                )
            except GitCommandError as exc:
                if exc.status == UNKNOWN_REF_STATUS:
                    return None
                raise

    async def recorded_commit(self) -> str | None:
        repository = await self.repository.sdk.get(
            kind=CoreRepository, id=str(self.repository.id), branch=self.destination_branch
        )
        # The API stores any text as the commit, and Git can compare only a full commit id.
        return readable_commit(repository.commit.value)

    def is_ancestor(self, *, ancestor: str, descendant: str) -> bool:
        gateway = GitAncestryGateway(
            repository_name=self.repository.name,
            repo=self.repository.get_git_repo_main(),
            timeout_seconds=self.local_timeout_seconds,
        )
        with self._bounded():
            try:
                # The comparison raises for a missing commit, which this answer reports as no.
                if not all(gateway.has_commit(commit=commit) for commit in (ancestor, descendant)):
                    return False
                return gateway.is_ancestor(ancestor_commit=ancestor, descendant_commit=descendant)
            except RepositoryError as exc:
                if _killed_command(error=exc) is not None:
                    raise
                # The detail can name a path on this worker, and users read the message in the push state.
                raise RepositoryError(
                    identifier=self.repository.name,
                    message=(
                        f"Unable to compare the commit {ancestor} against {descendant} in the clone of "
                        f"repository {self.repository.name} on this worker."
                    ),
                ) from exc

    def replay(self, *, base: str, commits: Sequence[str]) -> ReplayResult:
        worktree = self._destination_worktree()
        with self._bounded(worktree=worktree):
            worktree.git.reset("--hard", base, kill_after_timeout=self.local_timeout_seconds)
            for commit in commits:
                try:
                    self._merge(worktree=worktree, commit=commit)
                except GitCommandError as exc:
                    if _killed_command(error=exc) is not None:
                        raise
                    # A merge that stops on a conflict leaves itself in progress.
                    conflicted = Path(worktree.git_dir, "MERGE_HEAD").is_file()
                    if conflicted:
                        worktree.git.merge("--abort", kill_after_timeout=self.local_timeout_seconds)
                    worktree.git.reset("--hard", base, kill_after_timeout=self.local_timeout_seconds)
                    if not conflicted:
                        raise RepositoryError(
                            identifier=self.repository.name,
                            message=(
                                f"Unable to merge the commit {commit} into the branch {self.destination_branch} "
                                f"of repository {self.repository.name}."
                            ),
                        ) from exc
                    return ReplayResult(head=base, conflicting_commit=commit)
            head = worktree.git.rev_parse("HEAD", kill_after_timeout=self.local_timeout_seconds)
        return ReplayResult(head=str(head))

    async def push(self) -> None:
        """Push the worktree head to the destination branch of the remote.

        Raises:
            RepositoryError: The clone has no `origin` remote.

        """
        if not await self.repository.push(branch_name=self.destination_branch, timeout_seconds=PUSH_TIMEOUT_SECONDS):
            raise self._no_origin()

    def reset(self, *, commit: str) -> None:
        try:
            worktree = self._destination_worktree()
            self.repository._reset_to_pre_merge_commit(
                repo=worktree,
                dest_branch=self.destination_branch,
                commit_before=commit,
                timeout_seconds=self.local_timeout_seconds,
            )
            # A killed reset leaves its lock, and no other Git process runs in this worktree.
            _remove_index_lock(worktree=worktree)
        except Exception:
            # The failure that the reset recovers from must propagate, not this one.
            log.exception(
                "Failed to reset the worktree of branch %s of repository %s to %s.",
                self.destination_branch,
                self.repository.name,
                commit,
            )

    async def record(self, *, commit: str) -> None:
        with self._bounded():
            self.repository.create_commit_worktree(commit=commit, timeout_seconds=self.local_timeout_seconds)
        await self.repository.update_commit_value(branch_name=self.destination_branch, commit=commit)

    async def import_at(self, *, commit: str) -> None:
        plan = await self.repository.build_import_plan(infrahub_branch_name=self.destination_branch, commit=commit)
        await self.repository.apply_import_plan(plan)

    async def broadcast(self, *, commit: str) -> None:
        if not self.repository.location:
            return
        await self.message_bus.send(
            message=messages.RefreshGitFetch(
                meta=self._meta(),
                location=self.repository.location,
                repository_id=str(self.repository.id),
                repository_name=self.repository.name,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=self.destination_branch,
                infrahub_branch_id=self.destination_branch_id,
                commit=commit,
            )
        )

    async def delete_remote_branch(self, *, git_branch: str) -> None:
        try:
            await self.repository.delete_remote_branch(branch_name=git_branch, timeout_seconds=PUSH_TIMEOUT_SECONDS)
        except RepositoryError as exc:
            # The typed error keeps the Git error as its cause, and only that error tells that the branch is gone.
            cause = exc.__cause__
            if not (isinstance(cause, GitCommandError) and MISSING_REMOTE_BRANCH_TEXT in str(cause.stderr)):
                raise
        await self.notify_branch_deleted(git_branch=git_branch)

    async def notify_branch_deleted(self, *, git_branch: str) -> None:
        await self.message_bus.send(
            message=messages.RefreshGitRepositoryBranchDeleted(
                meta=self._meta(),
                repository_id=str(self.repository.id),
                repository_name=self.repository.name,
                repository_kind=InfrahubKind.REPOSITORY,
                branch_name=git_branch,
            )
        )

    def _destination_worktree(self) -> Repo:
        with self._bounded():
            worktrees = self.repository.get_worktrees(timeout_seconds=self.local_timeout_seconds)
        for worktree in worktrees:
            if worktree.identifier == self.destination_branch:
                return Repo(worktree.directory)
        raise RepositoryError(
            identifier=self.repository.name, message=f"Unable to find the worktree {self.destination_branch}."
        )

    def _merge(self, *, worktree: Repo, commit: str) -> None:
        if self.use_explicit_merge_commit:
            worktree.git.merge(commit, "--no-ff", m=MERGE_MESSAGE, kill_after_timeout=self.local_timeout_seconds)
        else:
            worktree.git.merge(commit, kill_after_timeout=self.local_timeout_seconds)

    @contextmanager
    def _bounded(self, *, worktree: Repo | None = None) -> Iterator[None]:
        """Replace the error of a local Git command that GitPython stopped at its time bound with one that names no path.

        Args:
            worktree: The worktree that the commands write to, whose index lock a killed command leaves.

        Raises:
            RepositoryError: GitPython stopped a command at its time bound.
            GitCommandError: A Git command failed for another reason, which passes unchanged, as does any other
                RepositoryError.

        """
        try:
            yield
        except (GitCommandError, RepositoryError) as exc:
            command = _killed_command(error=exc)
            if command is None:
                raise
            if worktree is not None:
                _remove_index_lock(worktree=worktree)
            raise RepositoryError(
                identifier=self.repository.name,
                message=f"The command {command} did not complete within {self.local_timeout_seconds:g} seconds.",
            ) from exc

    def _meta(self) -> Meta:
        return Meta(initiator_id=self.initiator_id, request_id=self.request_id)

    def _no_origin(self) -> RepositoryError:
        return RepositoryError(
            identifier=self.repository.name,
            message=f"The clone of repository {self.repository.name} on this worker has no origin.",
        )


def _killed_command(*, error: GitCommandError | RepositoryError) -> str | None:
    """Return the Git command, without its arguments, that GitPython stopped at its time bound, or None when it did not."""
    cause = error if isinstance(error, GitCommandError) else error.__cause__
    if isinstance(cause, GitCommandError) and KILLED_COMMAND_TEXT in str(cause.stderr):
        return f"git {cause.command[1]}"
    return None


def _remove_index_lock(*, worktree: Repo) -> None:
    Path(worktree.git_dir, "index.lock").unlink(missing_ok=True)
