from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import httpx

from infrahub.git.models import GitRepositoryDeliveryRetry
from infrahub.git.writeback.runs import delivery_run_tags
from infrahub.git.writeback.service import REPOSITORY_LOCK_NAMESPACE
from infrahub.log import get_run_logger
from infrahub.workflows.catalogue import GIT_REPOSITORY_DELIVERY_RETRY

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.git.writeback.ports import Clock, DeliveryRunQuery, DeliveryStatePort, RepositoryRef
    from infrahub.lock import InfrahubLockRegistry
    from infrahub.services.adapters.workflow import InfrahubWorkflow

log = get_run_logger()


class _Trigger(StrEnum):
    """Why the delivery of a repository needs a new run, worded for the log line of the submission."""

    STALE = "whose delivery lost its attempt"
    HELD_RELEASE = "whose held regeneration waits behind an empty queue"


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
            trigger = await self._trigger(repository=repository)
            if trigger is None:
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
        log.info("Submitted a delivery run of repository %s, %s.", repository.name, trigger)

        try:
            await self.state.touch(repository_id=repository.id)
        # A queued run already stops a second submission, so a failed touch must not hide the submission.
        except Exception:
            log.exception("Could not move the progress time of the delivery of repository %s.", repository.name)
        return True

    async def _trigger(self, *, repository: RepositoryRef) -> _Trigger | None:
        intent = await self.state.read(repository_id=repository.id)
        lock = self.lock_registry.get(name=repository.name, namespace=REPOSITORY_LOCK_NAMESPACE)
        lock_free = not await lock.locked()
        now = self.clock()
        if intent.is_stale(now=now, lock_free=lock_free, run_queued=False):
            trigger = _Trigger.STALE
        elif intent.release_waits(now=now):
            trigger = _Trigger.HELD_RELEASE
        else:
            return None

        try:
            run_queued = await self.runs.has_queued_run(repository_id=repository.id)
        # Without an answer, a run that waits to start looks lost, and a submission would only add to the queue.
        except (httpx.HTTPError, OSError) as exc:
            log.warning(
                "Could not ask the orchestrator whether a delivery run of repository %s waits, so none is submitted: %s",
                repository.name,
                exc,
            )
            return None
        return None if run_queued else trigger
