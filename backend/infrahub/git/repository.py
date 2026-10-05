from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID  # noqa: TC003

from cachetools import TTLCache
from cachetools.keys import hashkey
from cachetools_async import cached
from git.exc import BadName, GitCommandError
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.protocols import CoreReadOnlyRepository
from prefect import task
from prefect.cache_policies import NONE
from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import TERMINAL_BRANCH_STATUSES
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus, RepositoryOperationalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import (
    CommitNotFoundError,
    RepositoryError,
)
from infrahub.git.divergence.detector import RemoteDivergenceDetector
from infrahub.git.divergence.gateway import GitAncestryGateway
from infrahub.git.divergence.models import ReconciledBranch, RefClassification
from infrahub.git.graph_settings import resolve_graph_settings
from infrahub.git.integrator import InfrahubRepositoryIntegrator
from infrahub.log import get_run_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from git import Repo
    from infrahub_sdk.branch import BranchData
    from infrahub_sdk.client import InfrahubClient

    from infrahub.git.divergence.models import RefDivergence

log = get_run_logger()


def _describe_push_rejection(summary: str) -> str:
    """Prefix a per-ref push rejection summary with the likely reason the remote refused it.

    A rejected ref is not a failed ``git push`` command, so the ref's status summary is the
    only signal available to classify.
    """
    lowered = summary.lower()
    if any(marker in lowered for marker in ("hook declined", "protected branch", "permission denied", "not allowed")):
        return f"the remote refused the update (for example missing push permission or branch protection): {summary}"
    if any(marker in lowered for marker in ("non-fast-forward", "fetch first")):
        return f"the remote branch has commits that are missing locally (non-fast-forward): {summary}"
    return summary


@dataclass
class PendingObjectImport:
    """A repository object import waiting to run: which commit to import from and which Infrahub branch to import into."""

    infrahub_branch_name: str
    commit: str
    git_branch_name: str | None = None
    reconciled: ReconciledBranch | None = None
    """The branch a sync advanced to produce this import, None for an import no sync collected.

    It names the branch whose commit the sync wrote, which differs from ``infrahub_branch_name`` when
    the objects of a staging repository's trunk go to the staging branch.
    """


class ImportStep(StrEnum):
    """The phase of a branch synchronization in which a failure occurred."""

    COLLECTION = "collection"
    IMPORT = "import"


@dataclass
class FailedImport:
    """A branch that could not be synchronized, with the phase that failed and why."""

    branch_name: str
    step: ImportStep
    reason: str


@dataclass
class CollectedImports:
    """Outcome of the git/branch-setup phase of a sync.

    ``imports`` are the branches ready to have their objects imported. ``failed_imports`` are the
    branches whose git or branch setup failed, each carrying the phase that failed and the reason.
    ``skipped_branches`` are the remote branches left out because their name collides with Infrahub's
    default branch, and ``advanced_skipped_branches`` the subset of them whose remote head moved
    during this run's fetch.
    """

    imports: list[PendingObjectImport] = field(default_factory=list)
    failed_imports: list[FailedImport] = field(default_factory=list)
    skipped_branches: list[str] = field(default_factory=list)
    advanced_skipped_branches: list[str] = field(default_factory=list)

    @property
    def reconciled(self) -> list[ReconciledBranch]:
        """The branch each collected import advanced, and the commit it advanced to."""
        return [pending_import.reconciled for pending_import in self.imports if pending_import.reconciled is not None]


class InfrahubRepository(InfrahubRepositoryIntegrator):
    """Primary type of Git repository, with deep integration within Infrahub.

    Eventually we should rename this class InfrahubIntegratedRepository
    """

    default_branch: str = Field(
        ..., description="Remote branch this repository maps onto Infrahub's own default branch"
    )
    internal_status: RepositoryInternalStatus = Field(..., description="Internal status: Active, Inactive, Staging")

    @classmethod
    async def init(
        cls,
        *,
        id: str | UUID,
        name: str,
        client: InfrahubClient,
        infrahub_branch_name: str,
        commit: str | None = None,
        location: str | None = None,
    ) -> InfrahubRepository:
        """Build the repository object for an operation running on a given Infrahub branch."""
        self = await cls._build(
            id=id,
            name=name,
            client=client,
            infrahub_branch_name=infrahub_branch_name,
            location=location,
        )
        await self.initialize_local(commit=commit)
        return self

    @classmethod
    async def new(
        cls,
        *,
        id: str | UUID,
        name: str,
        client: InfrahubClient,
        infrahub_branch_name: str,
        location: str | None = None,
        update_commit_value: bool = True,
    ) -> InfrahubRepository:
        """Clone the repository locally for an operation running on a given Infrahub branch."""
        self = await cls._build(
            id=id,
            name=name,
            client=client,
            infrahub_branch_name=infrahub_branch_name,
            location=location,
        )
        await self.create_locally(
            checkout_ref=self.default_branch,
            infrahub_branch_name=infrahub_branch_name,
            update_commit_value=update_commit_value,
        )
        log.info("Created new repository locally: %s", self.name)
        return self

    @classmethod
    async def _build(
        cls,
        *,
        id: str | UUID,
        name: str,
        client: InfrahubClient,
        infrahub_branch_name: str,
        location: str | None,
    ) -> InfrahubRepository:
        """Resolve the repository's graph-held configuration once, then construct the object with it.

        A caller-supplied location wins over the node's: it is the one value a caller can
        legitimately know better, and both a local test remote and the add flow rely on that.
        """
        settings = await resolve_graph_settings(
            client=client,
            repository_id=str(id),
            repository_name=name,
            infrahub_branch_name=infrahub_branch_name,
        )
        return cls(
            id=id,
            name=name,
            client=client,
            infrahub_branch_name=infrahub_branch_name,
            default_branch=settings.default_branch,
            internal_status=settings.internal_status,
            location=location or settings.location,
        )

    async def resolve_checkout_ref(self) -> str:
        return self.default_branch

    def _get_mapped_remote_branch(self, branch_name: str) -> str:
        if branch_name != self.default_branch and branch_name == registry.default_branch:
            return self.default_branch
        return branch_name

    def _get_mapped_target_branch(self, branch_name: str) -> str:
        if branch_name == self.default_branch and branch_name != registry.default_branch:
            return registry.default_branch
        return branch_name

    def _resolve_worktree_identifier(self, branch_name: str) -> str:
        if branch_name == self.default_branch and branch_name != registry.default_branch:
            return "main"
        return branch_name

    def _collides_with_infrahub_default_branch(self, branch_name: str) -> bool:
        """Whether the branch is named like Infrahub's default branch while that name maps to another branch."""
        return branch_name == registry.default_branch and branch_name != self.default_branch

    def validate_remote_branch(self, branch_name: str) -> bool:
        """Process a remote branch to validate that we can use it safely.

        - Make sure that the branch name won't conflict with infrahub's default branch
        - Make sure that a representation of the branch can be created in the database
        - Warn (but do not block) when the branch would conflict with the default branch on merge
        """
        if self._collides_with_infrahub_default_branch(branch_name=branch_name):
            # If the default branch of Infrahub and the git repository differs we map the repository
            # default branch to that of Infrahub. In that scenario we can't import a branch from the
            # repository if it matches the default branch of Infrahub
            log.warning("Ignoring import of mismatched default branch %s of repository %s", branch_name, self.name)
            return False

        try:
            # Check if the branch can be created in the database
            Branch(name=branch_name)
        except PydanticValidationError as e:
            log.warning(
                "Git branch %s failed validation: %s",
                branch_name,
                ", ".join(error["msg"] for error in e.errors()),
            )
            return False

        # Surface a warning when the branch conflicts with the default branch so users
        # know a future merge will be rejected, but still allow the import to proceed.
        try:
            has_conflicts = self.has_conflicting_changes(target_branch=self.default_branch, source_branch=branch_name)
        except GitCommandError as exc:
            log.error(
                "Unable to determine merge conflicts for branch %s of repository %s: %s",
                branch_name,
                self.name,
                exc,
            )
            return True

        if has_conflicts:
            log.warning(
                f"Remote branch {branch_name} conflicts with {self.default_branch}; "
                "the merge will be rejected until the conflict is resolved upstream"
            )

        return True

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:
        branches = {}
        if remote:
            branches = self.get_branches_from_remote()
        else:
            branches = self.get_branches_from_local(include_worktree=False)

        if branch_name not in branches:
            raise ValueError(f"Branch {branch_name} not found.")

        return str(branches[branch_name].commit)

    async def create_branch_in_git(
        self, branch_name: str, branch_id: str | None = None, push_origin: bool = True
    ) -> bool:
        """Create new branch in the repository, assuming the branch has been created in the graph already."""
        response = await super().create_branch_in_git(branch_name=branch_name, branch_id=branch_id)
        if push_origin:
            await self.push(branch_name)

        return response

    def raise_if_branches_failed(self, failed_imports: list[FailedImport]) -> None:
        """Log every branch that failed before its import and surface every failed branch as a single error.

        A branch whose import failed is not logged again here, because the import already logged it once.

        Raises:
            RepositoryError: When at least one branch failed to synchronize.

        """
        if not failed_imports:
            return

        for failed in failed_imports:
            if failed.step is ImportStep.IMPORT:
                continue
            # extra= preserves step and reason as discrete LogRecord fields so log shippers
            # and alert rules can filter on them, even though the message already contains them.
            log.warning(
                "Failed to synchronize branch %s of repository %s at step %s: %s",
                failed.branch_name,
                self.name,
                failed.step.value,
                failed.reason,
                extra={
                    "repository": self.name,
                    "branch": failed.branch_name,
                    "step": failed.step.value,
                    "reason": failed.reason,
                },
            )

        branch_summaries = "; ".join(
            f"{failed.branch_name} (step={failed.step.value}): {failed.reason}" for failed in failed_imports
        )
        raise RepositoryError(
            identifier=self.name,
            message=f"Unable to synchronize the following branches of repository {self.name}: {branch_summaries}",
        )

    async def collect_pending_imports(
        self, staging_branch: str | None = None, graph_commits: Mapping[str, str | None] | None = None
    ) -> CollectedImports:
        """Run the git and branch-setup side of a sync and return the imports it produced.

        Brings the local clone in line with the remote and records the affected branches and their
        commits in the database, pinning a per-commit worktree for each. Returns one entry per branch
        whose objects still need importing into the graph, alongside the branches whose git setup
        failed and the reason each one failed.

        A branch worktree that moves is hard-reset onto the remote head, whatever the graph records, and
        a worktree that does not lead to that head loses the commits it held. Each branch is also
        classified against the commit the graph records for it, which is what tells a rewritten history
        apart from a fast-forward.

        Args:
            graph_commits: The commit the graph records for this repository, per Infrahub branch that
                can still record one. Without it no branch is classified, and a branch whose worktree
                already matches the remote is left alone even when the graph records another commit.

        Raises:
            RepositoryConnectionError: When the remote repository is unreachable.
            RepositoryCredentialsError: When the credentials for the remote repository are invalid.
            GraphQLError: When a branch or commit update against the database fails.

        """
        log.info("Starting the synchronization of %s.", self.name)

        # The remote-tracking ref still holds the previous fetch's head, which is what tells a skipped
        # branch that received a commit apart from one that is merely skipped again.
        colliding_branch = self._get_colliding_branch_name()
        head_before_fetch = self._get_remote_tracking_commit(colliding_branch) if colliding_branch else None

        await self.fetch()

        # Decided from the remote alone: a clone whose remote HEAD is the colliding branch holds it as a
        # local branch too, so the local/remote comparison below does not list it until it moves.
        skipped_branches, advanced_skipped_branches = self._find_skipped_branches(
            colliding_branch=colliding_branch, head_before_fetch=head_before_fetch
        )
        collected = CollectedImports(
            skipped_branches=skipped_branches, advanced_skipped_branches=advanced_skipped_branches
        )
        new_branches, updated_branches = await self.compare_local_remote()
        if graph_commits is not None:
            # An empty commit is one the graph never recorded.
            graph_commits = {name: commit or None for name, commit in graph_commits.items()}
            behind_in_graph = await self._find_branches_behind_in_graph(graph_commits=graph_commits)
            updated_branches = sorted({*updated_branches, *behind_in_graph})

        if not new_branches and not updated_branches:
            return collected

        log.debug("New Branches %s, Updated Branches %s for %s", new_branches, updated_branches, self.name)

        # Listing the branches costs a query, which a repository with nothing to import would pay every cycle.
        stages_trunk = (
            self.internal_status == RepositoryInternalStatus.STAGING
            and bool(staging_branch)
            and self.default_branch in updated_branches
        )
        if self.internal_status != RepositoryInternalStatus.ACTIVE and not stages_trunk:
            return collected

        remote_heads = {name: branch.commit for name, branch in self.get_branches_from_remote().items()}
        graph_branches = await self.sdk.branch.all()

        # TODO need to handle properly the situation when a branch is not valid.
        if self.internal_status == RepositoryInternalStatus.ACTIVE:
            # A branch that has been merged (or is being deleted) is read-only: recording its commit
            # would be rejected by the graph and abort the whole sync, so drop those branches here.
            new_branches, updated_branches = self._exclude_read_only_branches(
                new_branches=new_branches, updated_branches=updated_branches, graph_branches=graph_branches
            )

            for branch_name in new_branches:
                if self.validate_remote_branch(branch_name=branch_name):
                    await self._collect_new_branch(
                        collected=collected,
                        branch_name=branch_name,
                        remote_head=remote_heads.get(branch_name),
                        graph_commits=graph_commits,
                    )

            for branch_name in updated_branches:
                if self.validate_remote_branch(branch_name=branch_name):
                    await self._collect_updated_branch(
                        collected=collected,
                        branch_name=branch_name,
                        remote_heads=remote_heads,
                        graph_commits=graph_commits,
                        graph_branches=graph_branches,
                    )

        elif staging_branch:
            await self._queue_advanced_branch(
                collected=collected,
                branch_name=self.default_branch,
                import_branch=staging_branch,
                remote_heads=remote_heads,
                graph_commits=graph_commits,
                graph_branches=graph_branches,
                git_branch_name=self.default_branch,
            )

        return collected

    async def _collect_new_branch(
        self,
        collected: CollectedImports,
        branch_name: str,
        remote_head: str | None,
        graph_commits: Mapping[str, str | None] | None,
    ) -> None:
        """Create a branch this worker does not hold yet and queue its import.

        Git failures are recorded against the branch so the other branches are still collected.

        Raises:
            GraphQLError: When the graph rejects the branch or its commit for a reason other than the
                branch existing already.

        """
        infrahub_branch = self._get_mapped_target_branch(branch_name=branch_name)
        try:
            # Another worker may have imported a history the remote has since discarded.
            divergence = self._classify_against_graph(
                branch_name=branch_name, remote_head=remote_head, graph_commits=graph_commits
            )
        except RepositoryError as exc:
            # The classification only names a discarded history, so it must not keep the branch from being created.
            log.warning(
                "Unable to classify the new branch %s of repository %s against the graph: %s",
                branch_name,
                self.name,
                exc.message,
            )
            divergence = None

        try:
            try:
                branch = await self.create_branch_in_graph(branch_name=infrahub_branch)
            except GraphQLError as exc:
                if "already exist" not in exc.errors[0]["message"]:
                    raise
                branch = await self.sdk.branch.get(branch_name=infrahub_branch)

            await self.create_branch_in_git(branch_name=branch.name, branch_id=branch.id, push_origin=True)

            commit = self.get_commit_value(branch_name=branch_name, remote=False)
            self.create_commit_worktree(commit=commit)
            await self.update_commit_value(branch_name=infrahub_branch, commit=commit)
        except (RepositoryError, CommitNotFoundError, GitCommandError, ValueError) as exc:
            collected.failed_imports.append(
                FailedImport(branch_name=branch_name, step=ImportStep.COLLECTION, reason=str(exc))
            )
            return

        if divergence is not None and divergence.discarded_commit is not None:
            self._log_reconciliation(
                branch_name=branch_name, discarded_commit=divergence.discarded_commit, commit=commit
            )
        collected.imports.append(
            PendingObjectImport(
                infrahub_branch_name=infrahub_branch,
                commit=commit,
                reconciled=ReconciledBranch(
                    infrahub_branch_name=infrahub_branch,
                    infrahub_branch_id=branch.id,
                    commit=commit,
                    divergence=divergence,
                ),
            )
        )

    async def _collect_updated_branch(
        self,
        collected: CollectedImports,
        branch_name: str,
        remote_heads: dict[str, str],
        graph_commits: Mapping[str, str | None] | None,
        graph_branches: dict[str, BranchData],
    ) -> None:
        """Bring a branch this worker already holds onto the remote head and queue its import.

        Git failures are recorded against the branch so the other branches are still collected, while
        graph errors propagate.
        """
        try:
            await self._queue_advanced_branch(
                collected=collected,
                branch_name=branch_name,
                import_branch=self._get_mapped_target_branch(branch_name=branch_name),
                remote_heads=remote_heads,
                graph_commits=graph_commits,
                graph_branches=graph_branches,
            )
        except (RepositoryError, CommitNotFoundError, GitCommandError, ValueError) as exc:
            collected.failed_imports.append(
                FailedImport(branch_name=branch_name, step=ImportStep.COLLECTION, reason=str(exc))
            )

    async def _queue_advanced_branch(
        self,
        collected: CollectedImports,
        branch_name: str,
        import_branch: str,
        remote_heads: dict[str, str],
        graph_commits: Mapping[str, str | None] | None,
        graph_branches: dict[str, BranchData],
        git_branch_name: str | None = None,
    ) -> None:
        """Bring the worktree of a branch onto the remote head and queue its import into ``import_branch``.

        The branch is classified first, so a branch that git cannot classify keeps its worktree.

        Raises:
            RepositoryError: When git cannot classify the branch or move its worktree.
            ValueError: When the graph has no Infrahub branch for the branch, or it has no worktree here.

        """
        advanced_branch = self._get_mapped_target_branch(branch_name=branch_name)
        branch_id = self._get_branch_id(infrahub_branch=advanced_branch, graph_branches=graph_branches)
        remote_head = remote_heads.get(branch_name)
        divergence = self._classify_against_graph(
            branch_name=branch_name, remote_head=remote_head, graph_commits=graph_commits
        )
        commit = await self._advance_branch(branch_name=branch_name, remote_head=remote_head, divergence=divergence)
        if commit is not None:
            collected.imports.append(
                PendingObjectImport(
                    infrahub_branch_name=import_branch,
                    commit=commit,
                    git_branch_name=git_branch_name,
                    reconciled=ReconciledBranch(
                        infrahub_branch_name=advanced_branch,
                        infrahub_branch_id=branch_id,
                        commit=commit,
                        divergence=divergence,
                    ),
                )
            )

    async def _find_branches_behind_in_graph(self, graph_commits: Mapping[str, str | None]) -> list[str]:
        """Return the local branches whose commit in the graph is not the remote head.

        The local heads cannot show these: a worktree already on the remote head can still have its
        commit missing from the graph, and a changed default branch moves no ref at all.
        """
        if not self.has_origin:
            return []

        local_branches = self.get_branches_from_local(include_worktree=False)
        behind: list[str] = []
        for branch_name, remote_branch in (await self.get_filtered_remote_branches()).items():
            infrahub_branch = self._get_mapped_target_branch(branch_name=branch_name)
            if (
                branch_name not in local_branches
                or infrahub_branch not in graph_commits
                or self._collides_with_infrahub_default_branch(branch_name=branch_name)
            ):
                continue
            if graph_commits[infrahub_branch] != remote_branch.commit:
                behind.append(branch_name)
        return behind

    def _get_ancestry_gateway(self) -> GitAncestryGateway:
        return GitAncestryGateway(repository_name=self.name, repo=self.get_git_repo_main())

    def _classify_against_graph(
        self, branch_name: str, remote_head: str | None, graph_commits: Mapping[str, str | None] | None
    ) -> RefDivergence | None:
        if graph_commits is None:
            return None
        infrahub_branch = self._get_mapped_target_branch(branch_name=branch_name)
        return RemoteDivergenceDetector(gateway=self._get_ancestry_gateway()).classify(
            branch_name=branch_name,
            infrahub_branch_name=infrahub_branch,
            imported_commit=graph_commits.get(infrahub_branch),
            remote_head=remote_head,
            target_changed=False,
        )

    def _get_branch_id(self, infrahub_branch: str, graph_branches: dict[str, BranchData]) -> str:
        """Return the UUID of an Infrahub branch.

        Raises:
            ValueError: When the graph has no such branch, so no commit can be recorded for it.

        """
        if infrahub_branch not in graph_branches:
            raise ValueError(f"Infrahub has no branch {infrahub_branch} to record the commit of repository {self.name}")
        return graph_branches[infrahub_branch].id

    async def _advance_branch(
        self, branch_name: str, remote_head: str | None, divergence: RefDivergence | None
    ) -> str | None:
        """Hard-reset this worker's worktree of a branch onto the remote head and return the commit to import.

        The classification decides one case only: a worktree already on the remote head is left alone
        unless the graph records another commit. Returns None when there is nothing to import.

        Raises:
            ValueError: When the branch has no worktree on this worker.

        """
        if remote_head is None:
            return None

        worktree = self._get_branch_worktree(branch_name)
        worktree_head = str(worktree.head.commit) if worktree is not None else None
        if worktree_head == remote_head and (
            divergence is None or divergence.classification is RefClassification.UNCHANGED
        ):
            return None

        discarded_commit = divergence.discarded_commit if divergence is not None else None
        if (
            worktree_head is not None
            and worktree_head != remote_head
            and not self._get_ancestry_gateway().is_ancestor(
                ancestor_commit=worktree_head, descendant_commit=remote_head
            )
        ):
            discarded_commit = discarded_commit or worktree_head

        await self.reset_to_commit(branch_name=branch_name, commit=remote_head)
        if discarded_commit is not None:
            self._log_reconciliation(branch_name=branch_name, discarded_commit=discarded_commit, commit=remote_head)
        return remote_head

    def _log_reconciliation(self, branch_name: str, discarded_commit: str, commit: str) -> None:
        log.info(
            "Reconciled branch %s of repository %s with the remote history: %s was discarded and replaced by %s",
            branch_name,
            self.name,
            discarded_commit,
            commit,
            extra={
                "repository": self.name,
                "branch": branch_name,
                "discarded_commit": discarded_commit,
                "commit": commit,
            },
        )

    def _get_colliding_branch_name(self) -> str | None:
        """Return the name a remote branch cannot be imported under, or None when no name collides.

        Only an active repository imports branches, so only an active repository has one to skip.
        """
        if not self.has_origin or self.internal_status != RepositoryInternalStatus.ACTIVE:
            return None
        if not self._collides_with_infrahub_default_branch(branch_name=registry.default_branch):
            return None
        return registry.default_branch

    def _get_remote_tracking_commit(self, branch_name: str) -> str | None:
        """Return the commit of the branch's remote-tracking ref, or None when the clone has no such ref."""
        remote_refs = self.get_git_repo_main().remotes.origin.refs
        if branch_name not in remote_refs:
            return None
        return str(remote_refs[branch_name].commit)

    def _find_skipped_branches(
        self, colliding_branch: str | None, head_before_fetch: str | None
    ) -> tuple[list[str], list[str]]:
        """Return the skipped branches the remote holds, and the subset whose head moved during the fetch.

        A branch with no head before the fetch counts as moved: the clone is taken before that read, so a
        head missing from it means the branch was pushed to the remote since this clone last fetched.
        """
        if colliding_branch is None:
            return [], []
        head_after_fetch = self._get_remote_tracking_commit(colliding_branch)
        if head_after_fetch is None:
            return [], []
        advanced = [colliding_branch] if head_after_fetch != head_before_fetch else []
        return [colliding_branch], advanced

    def _exclude_read_only_branches(
        self, new_branches: list[str], updated_branches: list[str], graph_branches: dict[str, BranchData]
    ) -> tuple[list[str], list[str]]:
        """Drop the branches whose commit the graph cannot record.

        A branch in a terminal status (merged or being deleted) is read-only, so the graph rejects its
        commit. An updated branch whose Infrahub branch is gone has nowhere to record it, and its
        worktree would never move, so it would fail again on every cycle. A new branch is kept, because
        collecting it creates its Infrahub branch. The default branch is never terminal, so filtering
        here does not affect the staging-import path.
        """
        terminal_status_values = {status.value for status in TERMINAL_BRANCH_STATUSES}
        read_only = {name for name, branch in graph_branches.items() if branch.status.value in terminal_status_values}
        orphaned = [
            name for name in updated_branches if self._get_mapped_target_branch(branch_name=name) not in graph_branches
        ]
        if orphaned:
            log.debug("Ignoring branches %s of repository %s, which have no Infrahub branch", orphaned, self.name)
        return (
            [name for name in new_branches if self._get_mapped_target_branch(branch_name=name) not in read_only],
            [
                name
                for name in updated_branches
                if name not in orphaned and self._get_mapped_target_branch(branch_name=name) not in read_only
            ],
        )

    async def push(self, branch_name: str) -> bool:
        """Push a given branch to the remote Origin repository.

        Raises:
            RepositoryError: When the remote rejects the push at the ref level.
            RepositoryConnectionError: When the push fails to reach the remote.
            RepositoryCredentialsError: When authentication fails at push time.
            RepositoryPermissionError: When the credentials authenticate but lack write access.

        """
        if not self.has_origin:
            return False

        log.debug(
            "Pushing the latest update to the remote origin for the branch '%s' of repository %s.",
            branch_name,
            self.name,
        )

        repo = self.get_git_repo_worktree(identifier=branch_name)
        remote_branch = self._get_mapped_remote_branch(branch_name=branch_name)
        # Push the worktree HEAD, not the bare branch name: the local branch checked out in this
        # worktree may not be named after the remote branch (it differs when the repository's
        # default branch is not the Infrahub default), so a bare refspec would have no local source.
        try:
            push_infos = repo.remotes.origin.push(refspec=f"HEAD:refs/heads/{remote_branch}")
        except GitCommandError as exc:
            # A transport-level failure raises here with no porcelain status line to classify from flags.
            self._raise_enriched_error_static(
                error=exc, name=self.name, location=self.location, branch_name=branch_name, is_write_operation=True
            )
        for push_info in push_infos:
            if push_info.flags & push_info.ERROR:
                raise RepositoryError(
                    identifier=self.name,
                    message=(
                        f"Unable to push the branch {remote_branch} to the remote for repository {self.name}: "
                        f"{_describe_push_rejection(summary=push_info.summary.strip())}"
                    ),
                )

        return True

    async def merge(self, source_branch: str, dest_branch: str, push_remote: bool = True) -> str | Literal[False]:
        """Merge the source branch into the destination branch.

        After the rebase we need to resync the data

        On any failure the destination worktree is reset to its pre-merge commit. Whether the remote
        received the merge is not always knowable, since a push can be accepted just before the
        connection drops, so the reset leaves the destination either at the pre-merge state, where a
        later merge attempt re-derives the merge, or trailing the remote, which the periodic
        synchronization repairs by pulling the pushed merge commit and recording it.

        Raises:
            RepositoryError: When no worktree exists for the destination branch, when the
                underlying ``git merge`` command fails, or when the remote rejects the push.

        """
        repo = self.get_git_repo_worktree(identifier=dest_branch)

        commit_before = str(repo.head.commit)
        commit = self.get_commit_value(branch_name=source_branch, remote=False)

        try:
            if config.SETTINGS.git.use_explicit_merge_commit:
                repo.git.merge(commit, "--no-ff", m="Merged by Infrahub")
            else:
                repo.git.merge(commit)
        except GitCommandError as exc:
            repo.git.merge("--abort")
            raise RepositoryError(identifier=self.name, message=exc.stderr) from exc

        commit_after = str(repo.head.commit)

        if commit_after == commit_before:
            return False

        if self.has_origin and push_remote:
            pushed = False
            try:
                await self.push(branch_name=dest_branch)
                pushed = True
            finally:
                if not pushed:
                    # Left on the unpushed merge commit, a retry would find nothing to merge
                    # and return before ever reaching the push again.
                    self._reset_to_pre_merge_commit(repo=repo, dest_branch=dest_branch, commit_before=commit_before)

        recorded = False
        try:
            self.create_commit_worktree(commit_after)
            await self.update_commit_value(branch_name=dest_branch, commit=commit_after)
            recorded = True
        finally:
            if not recorded:
                # Trailing the remote is a state the periodic synchronization repairs by pulling
                # and recording the missing commit; a worktree left on a merge commit that is
                # recorded nowhere is never revisited.
                self._reset_to_pre_merge_commit(repo=repo, dest_branch=dest_branch, commit_before=commit_before)

        return str(commit_after)

    def _reset_to_pre_merge_commit(self, repo: Repo, dest_branch: str, commit_before: str) -> None:
        """Best-effort reset of a merge destination worktree while recovering from a failed merge.

        This never raises: the failure being recovered from is the one that explains why the merge
        was not delivered, and it must propagate unmasked.
        """
        try:
            repo.git.reset("--hard", commit_before)
        except Exception:
            # Raising here would replace the failure being recovered from with a less useful one.
            log.exception(
                "Failed to reset the worktree of branch %s of repository %s to %s while recovering from a "
                "failed merge; manual reconciliation may be required before the merge can be retried.",
                dest_branch,
                self.name,
                commit_before,
                extra={"repository": self.name, "branch": dest_branch},
            )

    async def rebase(
        self, branch_name: str, source_branch: str = "main", push_remote: bool = True
    ) -> str | Literal[False]:
        """Rebase the current branch with main.

        Technically we are not doing a Git rebase because it will change the git history
        We'll merge the content of the source_branch into branch_name instead to keep the history clear.

        TODO need to see how we manage conflict

        After the rebase we need to resync the data
        """
        return await self.merge(dest_branch=branch_name, source_branch=source_branch, push_remote=push_remote)


class InfrahubReadOnlyRepository(InfrahubRepositoryIntegrator):
    """Repository with only read-only access to the remote repo."""

    is_read_only: bool = True
    ref: str | None = Field(default=None, description="Ref to track on the external repository")

    @classmethod
    async def init(cls, commit: str | None = None, **kwargs: Any) -> InfrahubReadOnlyRepository:
        self = cls(**kwargs)
        await self.initialize_local(commit=commit)
        return self

    @classmethod
    async def new(cls, **kwargs: Any) -> InfrahubReadOnlyRepository:
        """Clone a read-only repository locally on the ref it tracks.

        Raises:
            ValueError: When the ref or the Infrahub branch is missing, either absent or None. The
                clone has to check something out, so neither can be defaulted.

        """
        if not kwargs.get("ref") or not kwargs.get("infrahub_branch_name"):
            raise ValueError("ref and infrahub_branch_name are mandatory to initialize a new Read-Only repository")

        self = cls(**kwargs)
        await self.create_locally(
            checkout_ref=await self.resolve_checkout_ref(), infrahub_branch_name=self.infrahub_branch_name
        )
        log.info("Created new repository locally: %s", self.name)
        return self

    async def resolve_checkout_ref(self) -> str:
        """Return the single ref this repository tracks, reading it from the graph when unset.

        Raises:
            RepositoryError: When the node carries no ref. The attribute is mandatory in the schema,
                so this is a corrupted node rather than a case to paper over with a default.

        """
        ref = self.ref
        if not ref:
            repository = await self.sdk.get(
                kind=CoreReadOnlyRepository,
                name__value=self.name,
                exclude=["tags", "credential"],
                raise_when_missing=True,
            )
            ref = repository.ref.value
            if not ref:
                raise RepositoryError(
                    identifier=self.name, message=f"Read-only repository {self.name} has no ref configured."
                )
            self.ref = ref

        return ref

    def _get_mapped_remote_branch(self, branch_name: str) -> str:
        return branch_name

    def _get_mapped_target_branch(self, branch_name: str) -> str:
        return branch_name

    def _resolve_worktree_identifier(self, branch_name: str) -> str:
        return branch_name

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str:  # noqa: ARG002
        """Always get the latest commit for this repository's ref on the remote.

        Raises:
            ValueError: When the configured ref cannot be resolved on the remote.

        """
        git_repo = self.get_git_repo_main()
        git_repo.remotes.origin.fetch()

        refs = (f"origin/{self.ref}", self.ref)
        commit = None
        for possible_ref in refs:
            try:
                commit = git_repo.commit(possible_ref)
                break
            except BadName:
                ...
        if not commit:
            log.error("No object found for refs %s on repository %s", refs, self.name)
            raise ValueError(f"Ref {self.ref} not found.")

        return str(commit)

    async def sync_from_remote(self, commit: str | None = None) -> bool:
        """Synchronize the repository from remote and update operational status.

        Args:
            commit: Specific commit to sync to. If None, fetches latest from remote.

        Returns:
            True if synchronization was performed, False if local state was already current.

        """
        if not commit:
            commit = self.get_commit_value(branch_name=self.ref, remote=True)
        local_branches = self.get_branches_from_local()
        if self.ref in local_branches and commit == local_branches[self.ref].commit:
            await self._update_operational_status(status=RepositoryOperationalStatus.ONLINE)
            return False
        self.create_commit_worktree(commit=commit)
        await self.import_objects_from_files(infrahub_branch_name=self.infrahub_branch_name, commit=commit)
        await self.update_commit_value(branch_name=self.infrahub_branch_name, commit=commit)
        await self._update_operational_status(status=RepositoryOperationalStatus.ONLINE)
        return True

    async def update_latest_commit(self) -> None:
        git_repo = self.get_git_repo_main()
        git_repo.remotes.origin.fetch(prune=True, tags=True, prune_tags=True)
        try:
            latest_commit = git_repo.git.rev_parse(f"origin/{self.ref}")
        except GitCommandError:
            try:
                latest_commit = git_repo.git.rev_parse(self.ref)
            except GitCommandError as err:
                log.error("No object found for ref %s on repository %s", self.ref, self.name)
                raise ValueError(f"Ref {self.ref} not found.") from err
        latest_commit = str(git_repo.commit(latest_commit))
        synced_from_remote = await self.sync_from_remote(commit=latest_commit)
        if not synced_from_remote:
            await self.update_commit_value(branch_name=self.infrahub_branch_name, commit=latest_commit)


@cached(
    TTLCache(maxsize=100, ttl=30),
    key=lambda *_, **kwargs: hashkey(
        kwargs.get("repository_id"),
        kwargs.get("name"),
        kwargs.get("repository_kind"),
        kwargs.get("commit"),
        kwargs.get("infrahub_branch_name"),
    ),
)
async def _get_initialized_repo(
    client: InfrahubClient,
    repository_id: str,
    name: str,
    repository_kind: str,
    infrahub_branch_name: str,
    commit: str | None = None,
) -> InfrahubReadOnlyRepository | InfrahubRepository:
    if repository_kind == InfrahubKind.REPOSITORY:
        return await InfrahubRepository.init(
            id=repository_id, name=name, commit=commit, client=client, infrahub_branch_name=infrahub_branch_name
        )

    if repository_kind == InfrahubKind.READONLYREPOSITORY:
        return await InfrahubReadOnlyRepository.init(
            id=repository_id, name=name, commit=commit, client=client, infrahub_branch_name=infrahub_branch_name
        )

    raise NotImplementedError(f"The repository kind {repository_kind} has not been implemented")


@task(
    name="Fetch repository commit",
    description="Retrieve a git repository at a given commit, if it does not already exist locally",
    cache_policy=NONE,
)
async def get_initialized_repo(
    client: InfrahubClient,
    repository_id: str,
    name: str,
    repository_kind: str,
    infrahub_branch_name: str,
    commit: str | None = None,
) -> InfrahubReadOnlyRepository | InfrahubRepository:
    return await _get_initialized_repo(
        client=client,
        repository_id=repository_id,
        name=name,
        repository_kind=repository_kind,
        infrahub_branch_name=infrahub_branch_name,
        commit=commit,
    )
