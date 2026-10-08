from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from infrahub.git.models import GitRepositoryDeliveryRetry
from infrahub.git.writeback.constants import STALE_AFTER_SECONDS
from infrahub.git.writeback.runs import delivery_run_tags
from infrahub.git.writeback.service import REPOSITORY_LOCK_NAMESPACE
from infrahub.log import get_run_logger
from infrahub.workflows.catalogue import GIT_REPOSITORY_DELIVERY_RETRY

if TYPE_CHECKING:
    from datetime import datetime

    from infrahub.context import InfrahubContext
    from infrahub.git.writeback.models import WritebackIntent
    from infrahub.git.writeback.ports import Clock, DeliveryRunQuery, DeliveryStatePort, RepositoryRef
    from infrahub.lock import InfrahubLockRegistry
    from infrahub.services.adapters.workflow import InfrahubWorkflow

log = get_run_logger()


class DeliveryRecoveryCheck:
    """Start a delivery run of a repository whose delivery lost its attempt, when nothing else will start one."""

    def __init__(
        self,
        state: DeliveryStatePort,
        workflow: InfrahubWorkflow,
        runs: DeliveryRunQuery,
        lock_registry: InfrahubLockRegistry,
        clock: Clock,
        context: InfrahubContext,
    ) -> None:
        self.state = state
        self.workflow = workflow
        self.runs = runs
        self.lock_registry = lock_registry
        self.clock = clock
        self.context = context

    async def run(self, *, repository: RepositoryRef) -> bool:
        """Submit a delivery run of the repository when its delivery needs one, and return whether it submitted.

        It never raises: a failure is logged, and the next cycle checks again.
        """
        try:
            if not await self._needs_run(repository=repository):
                return False
            await self.workflow.submit_workflow(
                workflow=GIT_REPOSITORY_DELIVERY_RETRY,
                context=self.context,
                parameters={
                    "model": GitRepositoryDeliveryRetry(
                        repository_id=repository.id, repository_name=repository.name, manual=False
                    )
                },
                tags=delivery_run_tags(repository.id),
            )
        # The synchronization of the repository runs after the check, so no failure of the check may stop it.
        except Exception:
            log.exception(
                "The delivery recovery check of repository %s failed; the next cycle checks again.", repository.name
            )
            return False
        log.info("Submitted a delivery run of repository %s, whose delivery lost its attempt.", repository.name)

        try:
            await self.state.touch(repository_id=repository.id)
        # A queued run already stops a second submission, so a failed touch must not hide the submission.
        except Exception:
            log.exception("Could not move the progress time of the delivery of repository %s.", repository.name)
        return True

    async def _needs_run(self, *, repository: RepositoryRef) -> bool:
        intent = await self.state.read(repository_id=repository.id)
        lock = self.lock_registry.get(name=repository.name, namespace=REPOSITORY_LOCK_NAMESPACE)
        lock_free = not await lock.locked()
        now = self.clock()
        if not (intent.is_stale(now=now, lock_free=lock_free, run_queued=False) or _release_waits(intent, now=now)):
            return False

        try:
            run_queued = await self.runs.has_queued_run(repository_id=repository.id)
        # Without an answer, a run that waits to start looks lost, and a submission would only add to the queue.
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Could not ask the orchestrator whether a delivery run of repository %s waits, so none is submitted: %s",
                repository.name,
                exc,
            )
            return False
        return not run_queued


def _release_waits(intent: WritebackIntent, *, now: datetime) -> bool:
    """Whether held regeneration that no live lease covers waits behind an empty queue, with no recent progress.

    A queue with merges is left to the stale check, so a delivery that waits for a user action gets no new run.
    """
    if intent.queue.entries or intent.held.lease_window(now=now, max_hold_seq=None).is_empty:
        return False
    last_progress_at = intent.progress.last_progress_at
    return last_progress_at is None or now - last_progress_at > timedelta(seconds=STALE_AFTER_SECONDS)
