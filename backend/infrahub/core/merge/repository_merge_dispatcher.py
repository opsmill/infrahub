from __future__ import annotations

from typing import TYPE_CHECKING

from neo4j.exceptions import DriverError, Neo4jError
from redis.exceptions import RedisError

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
from infrahub.exceptions import DatabaseError, DeliveryStateUnavailableError, QueryTimeoutError
from infrahub.git.commit_id import readable_commit
from infrahub.git.merge_readiness import GitMergeTarget, nothing_to_merge_in_git
from infrahub.git.models import GitRepositoryMerge
from infrahub.git.writeback.constants import ENQUEUE_RETRIES, ENQUEUE_RETRY_DELAYS_SECONDS
from infrahub.git.writeback.content import read_pending_merges
from infrahub.git.writeback.runs import delivery_run_tags
from infrahub.log import get_logger
from infrahub.workflows.catalogue import GIT_REPOSITORIES_MERGE

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.models import PendingMerge
    from infrahub.git.writeback.ports import DeliveryStatePort
    from infrahub.log import InfrahubLogger
    from infrahub.services.adapters.workflow import InfrahubWorkflow

# The store raises these while its database or the cache of its lock does not answer, which a later try can fix.
ENQUEUE_ERRORS: tuple[type[Exception], ...] = (
    DeliveryStateUnavailableError,
    DatabaseError,
    QueryTimeoutError,
    DriverError,
    Neo4jError,
    RedisError,
)


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
        state: DeliveryStatePort,
        sleep: Callable[[float], Awaitable[None]],
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.workflow = workflow
        self.state = state
        self.sleep = sleep
        self.log = logger or get_logger()

    async def merge_repositories(self, *, context: InfrahubContext) -> None:
        await self.merge_core_read_only_repositories()
        await self.merge_core_repositories(context=context)

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

    async def merge_core_repositories(self, *, context: InfrahubContext) -> None:
        repos = [repo for repo, _ in await list_shared_core_repositories(db=self.db, source_branch=self.source_branch)]
        pending_merges = (
            await read_pending_merges(
                db=self.db,
                source_branch=self.source_branch,
                default_branch=self.destination_branch,
                repository_ids=[
                    repo.id for repo in repos if repo.internal_status.value == RepositoryInternalStatus.ACTIVE.value
                ],
            )
            if self.source_branch.sync_with_git
            else {}
        )

        for repo in repos:
            if repo.internal_status.value == RepositoryInternalStatus.STAGING.value:
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
                continue

            if not self.source_branch.sync_with_git:
                continue

            pending_merge = pending_merges.get(repo.id)
            if pending_merge is None:
                self.log.info(
                    f"The merge of branch {self.source_branch.name} changes no content of repository "
                    f"{repo.name.value}, so nothing is pushed to its remote."
                )
                continue

            enqueued = await self._enqueue(repository_id=repo.id, repository_name=repo.name.value, entry=pending_merge)
            model = GitRepositoryMerge(
                repository_id=repo.id,
                repository_name=repo.name.value,
                internal_status=repo.internal_status.value,
                source_branch=self.source_branch.name,
                destination_branch=self.destination_branch.name,
                destination_branch_id=str(self.destination_branch.get_uuid()),
                repository_kind=InfrahubKind.REPOSITORY,
                # The Git merge can run after the source branch is deleted, so it gets the source commit from here.
                source_commit=readable_commit(repo.commit.value),
                pending_merge=pending_merge,
                pending_merge_enqueued=enqueued,
            )
            await self.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_MERGE,
                context=context,
                parameters={"model": model},
                tags=delivery_run_tags(repository_id=repo.id),
            )

    async def _enqueue(self, *, repository_id: str, repository_name: str, entry: PendingMerge) -> bool:
        """Queue the merge for its push to the remote, and return whether one of the tries returned."""
        retry_delays = iter(ENQUEUE_RETRY_DELAYS_SECONDS[:ENQUEUE_RETRIES])
        while True:
            try:
                await self.state.enqueue(repository_id=repository_id, entry=entry, widen=False)
            except ENQUEUE_ERRORS:
                delay = next(retry_delays, None)
                if delay is None:
                    self.log.exception(
                        f"The merge {entry.entry_id} was not queued for the push to repository {repository_name} "
                        "after the last try; the merge flow of the repository queues it, with a full regeneration held."
                    )
                    return False
                self.log.warning(
                    f"The merge {entry.entry_id} was not queued for the push to repository {repository_name}; "
                    f"the next try starts in {delay:g} seconds.",
                    exc_info=True,
                )
                await self.sleep(delay)
            else:
                self.log.info(
                    f"The merge of branch {self.source_branch.name} waits for its push to repository {repository_name}."
                )
                return True


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
