from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
from infrahub.git.commit_id import readable_commit
from infrahub.git.merge_readiness import GitMergeTarget, nothing_to_merge_in_git
from infrahub.git.models import GitRepositoryMerge
from infrahub.log import get_logger
from infrahub.workflows.catalogue import GIT_REPOSITORIES_MERGE

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.log import InfrahubLogger
    from infrahub.services.adapters.workflow import InfrahubWorkflow


class RepositoryMergeDispatcher:
    """Submit the repository-merge workflows for repositories shared between a branch and its destination.

    This does not perform the git merge itself; it builds the merge payloads and enqueues the
    workflows that do. It issues GraphQL writes to the default branch, so it must run only after the
    merge write-block has been lifted.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        workflow: InfrahubWorkflow,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.workflow = workflow
        self.log = logger or get_logger()

    async def merge_repositories(self) -> None:
        await self.merge_core_read_only_repositories()
        await self.merge_core_repositories()

    async def merge_core_read_only_repositories(self) -> None:
        repos_in_main_list = await NodeManager.query(schema=CoreReadOnlyRepository, db=self.db)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}

        repos_in_branch_list = await NodeManager.query(
            schema=CoreReadOnlyRepository, db=self.db, branch=self.source_branch
        )
        for repo in repos_in_branch_list:
            if repo.id not in repos_in_main:
                continue

            model = GitRepositoryMerge(
                repository_id=repo.id,
                repository_name=repo.name.value,
                source_branch=self.source_branch.name,
                destination_branch=self.destination_branch.name,
                destination_branch_id=str(self.destination_branch.get_uuid()),
                internal_status=repo.internal_status.value,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                # The merge copies this value to the trunk, so it must stay as the branch stores it.
                source_commit=repo.commit.value,
                source_ref=repo.ref.value,
            )
            await self.workflow.submit_workflow(workflow=GIT_REPOSITORIES_MERGE, parameters={"model": model})

    async def merge_core_repositories(self) -> None:
        for repo, repo_on_destination in await list_shared_core_repositories(
            db=self.db, source_branch=self.source_branch
        ):
            if self._needs_a_git_merge(repo=repo, repo_on_destination=repo_on_destination):
                # The Git merge can run after the source branch is deleted, so it gets the source commit from here.
                model = GitRepositoryMerge(
                    repository_id=repo.id,
                    repository_name=repo.name.value,
                    internal_status=repo.internal_status.value,
                    source_branch=self.source_branch.name,
                    destination_branch=self.destination_branch.name,
                    destination_branch_id=str(self.destination_branch.get_uuid()),
                    repository_kind=InfrahubKind.REPOSITORY,
                    source_commit=readable_commit(repo.commit.value),
                )
                await self.workflow.submit_workflow(workflow=GIT_REPOSITORIES_MERGE, parameters={"model": model})

    def _needs_a_git_merge(self, repo: CoreRepository, repo_on_destination: CoreRepository) -> bool:
        if repo.internal_status.value == RepositoryInternalStatus.STAGING.value:
            return True
        if not self.source_branch.sync_with_git:
            return False
        if not nothing_to_merge_in_git(
            source_commit=repo.commit.value, destination_commit=repo_on_destination.commit.value
        ):
            return True
        if repo.commit.value:
            self.log.info(
                f"Skipped the Git merge of repository {repo.name.value}: branch {self.source_branch.name} records "
                f"commit {repo.commit.value}, which the default branch records too, so there is nothing to push"
            )
        else:
            self.log.info(
                f"Skipped the Git merge of repository {repo.name.value}: neither branch {self.source_branch.name} "
                "nor the default branch records a commit, so there is nothing to push"
            )
        return False


async def list_shared_core_repositories(
    db: InfrahubDatabase, source_branch: Branch
) -> list[tuple[CoreRepository, CoreRepository]]:
    """Return each repository of the source branch that the default branch also holds and that is not inactive.

    Each one comes with its node on the default branch, which carries the commit that branch records.
    """
    repos_in_main = {repo.id: repo for repo in await NodeManager.query(schema=CoreRepository, db=db)}
    repos_in_branch = await NodeManager.query(schema=CoreRepository, db=db, branch=source_branch)
    return [
        (repo, repos_in_main[repo.id])
        for repo in repos_in_branch
        if repo.id in repos_in_main and repo.internal_status.value != RepositoryInternalStatus.INACTIVE.value
    ]


async def list_git_merge_targets(db: InfrahubDatabase, source_branch: Branch) -> list[GitMergeTarget]:
    """Return the repositories whose part of a merge of the source branch runs in Git."""
    if not source_branch.sync_with_git:
        return []
    return [
        GitMergeTarget(
            name=repo.name.value,
            location=repo.location.value,
            remote_source_branch=source_branch.name,
            remote_trunk=repo_on_destination.default_branch.value,
            source_commit=readable_commit(repo.commit.value),
            destination_commit=readable_commit(repo_on_destination.commit.value),
            nothing_to_merge=nothing_to_merge_in_git(
                source_commit=repo.commit.value, destination_commit=repo_on_destination.commit.value
            ),
        )
        for repo, repo_on_destination in await list_shared_core_repositories(db=db, source_branch=source_branch)
        if repo.internal_status.value == RepositoryInternalStatus.ACTIVE.value
    ]
