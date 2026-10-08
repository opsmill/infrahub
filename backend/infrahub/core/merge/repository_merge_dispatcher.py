from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
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
        await self.merge_core_read_only_repositories(context=context)
        await self.merge_core_repositories(context=context)

    async def merge_core_read_only_repositories(self, *, context: InfrahubContext) -> None:
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
            )
            await self.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_MERGE, context=context, parameters={"model": model}
            )

    async def merge_core_repositories(self, *, context: InfrahubContext) -> None:
        # Collect all Repositories in Main because we'll need the commit in Main for each one.
        repos_in_main_list = await NodeManager.query(schema=CoreRepository, db=self.db)
        repos_in_main = {repo.id: repo for repo in repos_in_main_list}

        repos_in_branch_list = await NodeManager.query(schema=CoreRepository, db=self.db, branch=self.source_branch)
        repos = [
            repo
            for repo in repos_in_branch_list
            if repo.id in repos_in_main
            and (
                repo.internal_status.value == RepositoryInternalStatus.STAGING.value
                or (
                    repo.internal_status.value == RepositoryInternalStatus.ACTIVE.value
                    and self.source_branch.sync_with_git
                )
            )
        ]
        pending_merges = await self._read_pending_merges(
            repository_ids=[
                repo.id for repo in repos if repo.internal_status.value == RepositoryInternalStatus.ACTIVE.value
            ]
        )

        for repo in repos:
            model = GitRepositoryMerge(
                repository_id=repo.id,
                repository_name=repo.name.value,
                internal_status=repo.internal_status.value,
                source_branch=self.source_branch.name,
                destination_branch=self.destination_branch.name,
                destination_branch_id=str(self.destination_branch.get_uuid()),
                repository_kind=InfrahubKind.REPOSITORY,
            )
            if repo.internal_status.value == RepositoryInternalStatus.STAGING.value:
                await self.workflow.submit_workflow(
                    workflow=GIT_REPOSITORIES_MERGE, context=context, parameters={"model": model}
                )
                continue

            if pending_merges is not None:
                pending_merge = pending_merges.get(repo.id)
                if pending_merge is None:
                    self.log.info(
                        f"The merge of branch {self.source_branch.name} changes no content of repository "
                        f"{repo.name.value}, so nothing is pushed to its remote."
                    )
                    continue
                enqueued = await self._enqueue(
                    repository_id=repo.id, repository_name=repo.name.value, entry=pending_merge
                )
                model = model.model_copy(update={"pending_merge": pending_merge, "pending_merge_enqueued": enqueued})
            await self.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_MERGE,
                context=context,
                parameters={"model": model},
                tags=delivery_run_tags(repository_id=repo.id),
            )

    async def _read_pending_merges(self, *, repository_ids: list[str]) -> dict[str, PendingMerge] | None:
        """Return the new queue entry of each repository whose content the merge changes, or None when the read fails."""
        try:
            return await read_pending_merges(
                db=self.db,
                source_branch=self.source_branch,
                default_branch=self.destination_branch,
                repository_ids=repository_ids,
            )
        except Exception:
            # The graph merge is done, so the merge flow of each repository still runs and reads the content itself.
            self.log.exception(
                f"Unable to read which repositories the merge of branch {self.source_branch.name} changes; "
                "the merge flow of each repository reads it again."
            )
            return None

    async def _enqueue(self, *, repository_id: str, repository_name: str, entry: PendingMerge) -> bool:
        """Queue the merge for its push to the remote, and return whether a try succeeded."""
        retry_delays = iter(ENQUEUE_RETRY_DELAYS_SECONDS[:ENQUEUE_RETRIES])
        while True:
            try:
                await self.state.enqueue(repository_id=repository_id, entry=entry, widen=False)
            except Exception:
                # The graph merge is done, so no failure may stop the merge flow, which queues the entry again.
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
