"""Deciding whether a read-only repository's tracked refs have moved, and converging the pool.

The check never writes the tracked commit and never imports. It compares the local view of each
tracked ref against the remote, and when they differ it brings the new objects in while leaving
every worker on the commit Infrahub already tracks.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import RepositoryError
from infrahub.git.state.cache_keys import (
    REFS_CHECK_LAST_TTL_SECONDS,
    refs_check_due_key,
    refs_check_last_key,
    refs_check_running_key,
)
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.worker import WORKER_IDENTITY

from .models import RefMovement, RefsCheckOutcome, RefsCheckResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.lock import InfrahubLockRegistry
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

    from ..models import GitReadOnlyRepositoryCheckRefs
    from .gateway import CheckRefFormat, RepositoryRefsGateway

log = get_logger()


class RefNameValidator:
    """Refuses ref names git would reject, and option-like names before git is invoked at all."""

    def __init__(self, check_ref_format: CheckRefFormat) -> None:
        self._check_ref_format = check_ref_format

    async def is_valid(self, ref: str) -> bool:
        if not ref or ref.startswith("-"):
            return False
        return await asyncio.to_thread(self._check_ref_format, ref)


class RefsCheckScheduler:
    """Spaces repeated checks of the same repository by one configured interval.

    The due key is both the record and the spacing: it survives for one interval, so a repository
    selected here is passed over until it expires. Keys already written keep the interval they were
    written with, so a change takes effect as each one expires rather than all at once.
    """

    def __init__(self, *, cache: InfrahubCache, interval_seconds: int, retry_seconds: int) -> None:
        self._cache = cache
        self._interval_seconds = interval_seconds
        self._retry_seconds = retry_seconds

    async def select_due(
        self, models: Sequence[GitReadOnlyRepositoryCheckRefs]
    ) -> list[GitReadOnlyRepositoryCheckRefs]:
        due = []
        for model in models:
            claimed = await self._cache.set(
                key=refs_check_due_key(model.repository_id),
                value=datetime.now(tz=UTC).isoformat(),
                expires=self._interval_seconds,
                not_exists=True,
            )
            if claimed:
                due.append(model)
        return due

    async def retry_soon(self, repository_id: str) -> None:
        """Bring the next check of a repository forward after a failed one.

        Shortening the due key rather than dropping it is what keeps a permanently broken
        repository from being retried on every tick of the schedule, where it would occupy a
        concurrency slot at the expense of repositories that can still be checked.
        """
        await self._cache.set(
            key=refs_check_due_key(repository_id),
            value=datetime.now(tz=UTC).isoformat(),
            expires=self._retry_seconds,
        )


class ReadOnlyRepositoryRefsChecker:
    """Checks one read-only repository's remote for movement of the refs it tracks.

    The claim, the listing and the convergence are the whole of the check: nothing here writes the
    tracked commit and nothing here imports.
    """

    def __init__(
        self,
        *,
        cache: InfrahubCache,
        message_bus: InfrahubMessageBus,
        lock_registry: InfrahubLockRegistry,
        gateway: RepositoryRefsGateway,
        ref_validator: RefNameValidator,
        scheduler: RefsCheckScheduler,
        claim_ttl_seconds: int,
        detect_timeout_seconds: float,
    ) -> None:
        self._cache = cache
        self._message_bus = message_bus
        self._lock_registry = lock_registry
        self._gateway = gateway
        self._ref_validator = ref_validator
        self._scheduler = scheduler
        self._claim_ttl_seconds = claim_ttl_seconds
        self._detect_timeout_seconds = detect_timeout_seconds

    async def check(self, model: GitReadOnlyRepositoryCheckRefs, *, run_id: str) -> RefsCheckResult:
        claimed = await self._cache.set(
            key=refs_check_running_key(model.repository_id),
            value=run_id,
            expires=self._claim_ttl_seconds,
            not_exists=True,
        )
        if not claimed:
            holder = await self._cache.get(key=refs_check_running_key(model.repository_id))
            log.info(
                "Skipping refs check, another run holds the repository",
                repository=model.repository_name,
                held_by=holder,
            )
            return RefsCheckResult(
                repository_id=model.repository_id,
                repository_name=model.repository_name,
                outcome=RefsCheckOutcome.SKIPPED_CLAIMED,
                claimed_by=holder,
            )

        try:
            invalid_ref = await self._first_invalid_ref(model)
            if invalid_ref is not None:
                reason = f"Refusing to check the invalid ref '{invalid_ref}'."
                log.warning("Refs check refused", repository=model.repository_name, reason=reason)
                return await self._record_failure(model, reason=reason, contacted_remote=False)

            # The bound covers the listing only. Convergence takes the repository lock, which
            # carries no expiry, so a cancellation landing inside it could leave that lock held
            # for good and block every later operation on the repository.
            async with asyncio.timeout(self._detect_timeout_seconds):
                movements = await self._detect_movements(model)
            if movements:
                # Convergence is unbounded, so take the claim's lease again rather than spending
                # what the listing left of it.
                await self._renew_claim(model, run_id=run_id)
                await self._converge(model, movements)
        except TimeoutError:
            reason = f"Timed out after {self._detect_timeout_seconds}s reading the remote refs."
            log.warning("Refs check timed out", repository=model.repository_name, reason=reason)
            return await self._record_failure(model, reason=reason, contacted_remote=True)
        except RepositoryError as exc:
            reason = str(exc)
            log.warning("Refs check failed", repository=model.repository_name, reason=reason)
            return await self._record_failure(model, reason=reason, contacted_remote=True)
        finally:
            # Release before stamping: the claim suppresses every later check until it expires,
            # where a missing check time only leaves one reading absent.
            await self._release_claim(model, run_id=run_id)
            await self._record_check_time(model)

        return RefsCheckResult(
            repository_id=model.repository_id,
            repository_name=model.repository_name,
            outcome=RefsCheckOutcome.COMPLETED,
            movements=tuple(movements),
            contacted_remote=True,
        )

    async def _renew_claim(self, model: GitReadOnlyRepositoryCheckRefs, *, run_id: str) -> None:
        await self._cache.set(
            key=refs_check_running_key(model.repository_id),
            value=run_id,
            expires=self._claim_ttl_seconds,
        )

    async def _release_claim(self, model: GitReadOnlyRepositoryCheckRefs, *, run_id: str) -> None:
        """Drop the claim only while it is still this run's.

        A check that outlived its claim must not delete the one a later run has since taken, which
        would leave that run unprotected and admit the overlapping fetch the claim exists to stop.
        """
        holder = await self._cache.get(key=refs_check_running_key(model.repository_id))
        if holder is not None and holder != run_id:
            log.info(
                "Leaving the refs check claim in place, it now belongs to another run",
                repository=model.repository_name,
                held_by=holder,
            )
            return
        await self._cache.delete(key=refs_check_running_key(model.repository_id))

    async def _first_invalid_ref(self, model: GitReadOnlyRepositoryCheckRefs) -> str | None:
        for ref in self._tracked_ref_names(model):
            if not await self._ref_validator.is_valid(ref):
                return ref
        return None

    async def _record_failure(
        self, model: GitReadOnlyRepositoryCheckRefs, *, reason: str, contacted_remote: bool
    ) -> RefsCheckResult:
        await self._scheduler.retry_soon(model.repository_id)
        return RefsCheckResult(
            repository_id=model.repository_id,
            repository_name=model.repository_name,
            outcome=RefsCheckOutcome.FAILED,
            failure_reason=reason,
            contacted_remote=contacted_remote,
        )

    async def _record_check_time(self, model: GitReadOnlyRepositoryCheckRefs) -> None:
        """Stamp when the remote was last looked at, best effort.

        This runs in a ``finally``, so letting it raise would discard the outcome of the check it
        is stamping and replace the reason a check failed with the reason the stamp failed.
        """
        try:
            await self._cache.set(
                key=refs_check_last_key(model.repository_id),
                value=datetime.now(tz=UTC).isoformat(),
                expires=REFS_CHECK_LAST_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not record the refs check time", repository=model.repository_name, reason=str(exc))

    async def _detect_movements(self, model: GitReadOnlyRepositoryCheckRefs) -> list[RefMovement]:
        movements: list[RefMovement] = []
        for ref in self._tracked_ref_names(model):
            local_head = await self._gateway.read_local_head(model, ref)
            remote_head = await self._gateway.read_remote_head(model, ref)
            if remote_head is None:
                log.info("Tracked ref is absent from the remote", repository=model.repository_name, ref=ref)
                continue
            if remote_head == local_head:
                continue

            log.info(
                "Tracked ref moved upstream",
                repository=model.repository_name,
                ref=ref,
                previous_head=local_head,
                new_head=remote_head,
            )
            movements.append(RefMovement(ref=ref, previous_head=local_head, new_head=remote_head))

        return movements

    @staticmethod
    def _tracked_ref_names(model: GitReadOnlyRepositoryCheckRefs) -> list[str]:
        """Return each distinct tracked ref once, so two branches on one ref cost one listing."""
        return list(dict.fromkeys(tracked.ref for tracked in model.refs))

    async def _converge(self, model: GitReadOnlyRepositoryCheckRefs, movements: list[RefMovement]) -> None:
        moved_refs = {movement.ref for movement in movements}
        async with self._lock_registry.get(name=model.repository_name, namespace="repository"):
            await self._gateway.fetch(model)

            for tracked in model.refs:
                if tracked.ref not in moved_refs:
                    continue
                if tracked.commit is None:
                    # Nothing imported on this branch yet, so there is no commit to pin the pool
                    # to; an unpinned broadcast would move every worker onto the new head.
                    log.info(
                        "Not converging a branch with no imported commit",
                        repository=model.repository_name,
                        branch=tracked.infrahub_branch_name,
                        ref=tracked.ref,
                    )
                    continue
                # Pinned to the tracked commit so no worker moves off it while picking up the
                # objects the moved ref brought in.
                await self._message_bus.send(
                    message=messages.RefreshGitFetch(
                        meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
                        location=model.location,
                        repository_id=model.repository_id,
                        repository_name=model.repository_name,
                        repository_kind=InfrahubKind.READONLYREPOSITORY,
                        infrahub_branch_name=tracked.infrahub_branch_name,
                        infrahub_branch_id=tracked.infrahub_branch_id,
                        commit=tracked.commit,
                    )
                )
