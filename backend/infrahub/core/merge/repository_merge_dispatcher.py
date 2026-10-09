from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
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
        state_for_session: Callable[[InfrahubDatabase], DeliveryStatePort],
        sleep: Callable[[float], Awaitable[None]],
        logger: InfrahubLogger | None = None,
    ) -> None:
        """Build the dispatcher.

        Args:
            state_for_session: Builds the delivery state on a database session, because the merges of all
                repositories queue at once and one session serves one of them at a time.

        """
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.workflow = workflow
        self.state_for_session = state_for_session
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
        repos = [
            repo
            for repo, _ in await list_shared_core_repositories(db=self.db, source_branch=self.source_branch)
            if repo.internal_status.value == RepositoryInternalStatus.STAGING.value or self.source_branch.sync_with_git
        ]
        pending_merges = await self._read_pending_merges(
            repository_ids=[
                repo.id for repo in repos if repo.internal_status.value == RepositoryInternalStatus.ACTIVE.value
            ]
        )
        queueable = pending_merges or {}
        enqueued = await self._enqueue_all(
            entries={repo.id: (repo.name.value, queueable[repo.id]) for repo in repos if repo.id in queueable}
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
                # The Git merge can run after the source branch is deleted, so it gets the source commit from here.
                source_commit=readable_commit(repo.commit.value),
            )
            if repo.internal_status.value == RepositoryInternalStatus.STAGING.value:
                await self.workflow.submit_workflow(workflow=GIT_REPOSITORIES_MERGE, parameters={"model": model})
                continue

            if pending_merges is not None:
                pending_merge = pending_merges.get(repo.id)
                if pending_merge is None:
                    self.log.info(
                        f"The merge of branch {self.source_branch.name} changes no content of repository "
                        f"{repo.name.value}, so nothing is pushed to its remote."
                    )
                    continue
                model = model.model_copy(
                    update={"pending_merge": pending_merge, "pending_merge_enqueued": enqueued[repo.id]}
                )
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

    async def _enqueue_all(self, *, entries: dict[str, tuple[str, PendingMerge]]) -> dict[str, bool]:
        """Queue the merge of every repository, and return by repository id whether a try succeeded.

        The branch merge holds the global merge lock meanwhile, so the retries of all repositories run at once.
        """
        results = await asyncio.gather(
            *(
                self._enqueue(repository_id=repository_id, repository_name=repository_name, entry=entry)
                for repository_id, (repository_name, entry) in entries.items()
            )
        )
        return dict(zip(entries, results, strict=True))

    async def _enqueue(self, *, repository_id: str, repository_name: str, entry: PendingMerge) -> bool:
        """Queue the merge for its push to the remote, and return whether a try succeeded."""
        retry_delays = iter(ENQUEUE_RETRY_DELAYS_SECONDS[:ENQUEUE_RETRIES])
        while True:
            try:
                async with self.db.start_session() as session:
                    await self.state_for_session(session).enqueue(repository_id=repository_id, entry=entry, widen=False)
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
