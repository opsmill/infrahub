from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from infrahub.git.writeback.constants import BARRIER_STATE_READ_DELAYS_SECONDS, BARRIER_STATE_READ_RETRIES
from infrahub.git.writeback.models import HeldRegeneration, HeldWiden
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from infrahub.core.constants import FullRegenerationReason
    from infrahub.git.writeback.models import HoldReceipt
    from infrahub.git.writeback.ports import DeliveryStatePort
    from infrahub.services.adapters.cache import InfrahubCache

log = get_logger()


@dataclass(frozen=True, eq=False)
class OwnedRegeneration[RequestT: BaseModel]:
    """One candidate of the barrier: what to hold, the repository that owns it, and the request to dispatch.

    Candidates compare by identity, so a lookup never compares their requests field by field.
    """

    repository_id: str | None
    """None when the owner is not known, which holds the candidate under every pending repository."""
    held: HeldRegeneration
    request: RequestT
    union: Callable[[BaseModel, BaseModel], BaseModel] | None
    """Joins the requests of two holds of one item; None keeps no narrowed request for a repeated hold."""


class NarrowedHoldCache:
    """The narrowed request of each held item, kept for a bounded time under the sequence of its hold."""

    def __init__(self, cache: InfrahubCache, ttl_seconds: int, max_bytes: int) -> None:
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.max_bytes = max_bytes

    async def put(self, *, repository_id: str, hold_seq: int, identifier: str, request: BaseModel) -> None:
        """Keep the request under the hold; a request above the size bound is not kept."""
        await self._write(
            key=self._key(repository_id=repository_id, hold_seq=hold_seq, identifier=identifier), request=request
        )

    async def merge_put(
        self,
        *,
        repository_id: str,
        previous_seq: int,
        hold_seq: int,
        identifier: str,
        request: BaseModel,
        union: Callable[[BaseModel, BaseModel], BaseModel],
    ) -> None:
        """Keep the union of the request and the entry of the previous hold, or nothing when that entry is missing."""
        previous = await self.get(
            repository_id=repository_id, hold_seq=previous_seq, identifier=identifier, model=type(request)
        )
        if previous is None:
            return
        await self._write(
            key=self._key(repository_id=repository_id, hold_seq=hold_seq, identifier=identifier),
            request=union(previous, request),
        )

    async def get[ModelT: BaseModel](
        self, *, repository_id: str, hold_seq: int, identifier: str, model: type[ModelT]
    ) -> ModelT | None:
        """Return the request kept under the hold, or None when it is missing, expired or cannot be read."""
        key = self._key(repository_id=repository_id, hold_seq=hold_seq, identifier=identifier)
        try:
            value = await self.cache.get(key=key)
            return None if value is None else model.model_validate_json(value)
        # A miss only widens the release, so a failed read must not stop it.
        except Exception:
            log.warning("Could not read a narrowed held request; treating it as a miss", key=key, exc_info=True)
            return None

    async def _write(self, *, key: str, request: BaseModel) -> None:
        value = request.model_dump_json()
        if len(value.encode()) > self.max_bytes:
            return
        await self.cache.set(key=key, value=value, expires=self.ttl_seconds)

    def _key(self, *, repository_id: str, hold_seq: int, identifier: str) -> str:
        return f"repository-delivery:held:{repository_id}:{hold_seq}:{identifier}"


class RegenerationBarrier:
    """Hold the regeneration that a repository owns while its merges wait for their push, and admit the rest.

    It never raises: when the delivery state cannot be read or updated after the retries, it admits every
    candidate, or returns no holder of a marker. The holds written before the failure stay.
    """

    def __init__(
        self,
        state: DeliveryStatePort,
        narrowed: NarrowedHoldCache,
        default_branch_name: str,
        sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        self.state = state
        self.narrowed = narrowed
        self.default_branch_name = default_branch_name
        self.sleep = sleep

    async def admit[RequestT: BaseModel](
        self,
        *,
        branch: str,
        candidates: Sequence[OwnedRegeneration[RequestT]],
        releasing: str | None,
    ) -> list[OwnedRegeneration[RequestT]]:
        """Hold the candidates of each repository with a pending delivery, and return the candidates to dispatch now.

        Args:
            releasing: The repository whose held regeneration is being released, so its candidates are admitted.

        """
        if branch != self.default_branch_name:
            return list(candidates)
        return await self._with_retries(
            attempt=lambda: self._partition(candidates=candidates, releasing=releasing),
            fallback=list(candidates),
            branch=branch,
            gave_up=(
                "Could not read or update the delivery state; dispatching every candidate, "
                "and the holds written before the failure stay"
            ),
            repository_ids=sorted(
                {candidate.repository_id for candidate in candidates if candidate.repository_id is not None}
            ),
        )

    async def hold_widen(
        self,
        *,
        branch: str,
        scope: Literal["all", "terminals"],
        reason: FullRegenerationReason,
        releasing: str | None,
    ) -> list[str]:
        """Hold a marker under each pending repository except `releasing`, and return the sorted ids that hold it.

        A blanket regeneration excludes the returned repositories, because the release of each marker regenerates them.
        """
        if branch != self.default_branch_name:
            return []
        widen = HeldWiden(scope=scope, reason=reason, hold_seq=0)
        return await self._with_retries(
            attempt=lambda: self._hold_widen(widen=widen, releasing=releasing),
            fallback=[],
            branch=branch,
            gave_up=(
                "Could not read or update the delivery state; regenerating every repository, "
                "and the markers held before the failure stay"
            ),
            scope=scope,
            reason=reason,
        )

    async def _with_retries[ResultT](
        self,
        *,
        attempt: Callable[[], Awaitable[ResultT]],
        fallback: ResultT,
        branch: str,
        gave_up: str,
        **context: object,
    ) -> ResultT:
        delays = iter(BARRIER_STATE_READ_DELAYS_SECONDS[:BARRIER_STATE_READ_RETRIES])
        while True:
            try:
                return await attempt()
            # Nothing retries the flows that consult the barrier, so a raise would drop their regeneration.
            except Exception:
                delay = next(delays, None)
                if delay is None:
                    log.exception(gave_up, branch=branch, **context)
                    return fallback
                log.warning(
                    "Could not read or update the delivery state; trying again", branch=branch, exc_info=True, **context
                )
                await self.sleep(delay)

    async def _hold_widen(self, *, widen: HeldWiden, releasing: str | None) -> list[str]:
        held = HeldRegeneration(widen=widen)
        holders = sorted(await self.state.pending_repository_ids() - {releasing})
        return [
            repository_id
            for repository_id in holders
            if await self.state.hold(repository_id=repository_id, held=held) is not None
        ]

    async def _partition[RequestT: BaseModel](
        self, *, candidates: Sequence[OwnedRegeneration[RequestT]], releasing: str | None
    ) -> list[OwnedRegeneration[RequestT]]:
        pending = await self.state.pending_repository_ids()
        if not pending:
            return list(candidates)
        holders = sorted(pending - {releasing})
        owners: list[list[str]] = []
        held_by_repository: dict[str, list[OwnedRegeneration[RequestT]]] = {}
        for candidate in candidates:
            if candidate.repository_id is None:
                candidate_owners = holders
            elif candidate.repository_id == releasing or candidate.repository_id not in pending:
                candidate_owners = []
            else:
                candidate_owners = [candidate.repository_id]
            owners.append(candidate_owners)
            for repository_id in candidate_owners:
                held_by_repository.setdefault(repository_id, []).append(candidate)

        settled: set[str] = set()
        for repository_id, held in held_by_repository.items():
            receipt = await self.state.hold(repository_id=repository_id, held=_combined(candidates=held))
            if receipt is None:
                settled.add(repository_id)
            else:
                await self._keep_narrowed(repository_id=repository_id, receipt=receipt, candidates=held)
        return [
            candidate
            for candidate, candidate_owners in zip(candidates, owners, strict=True)
            if settled.issuperset(candidate_owners)
        ]

    async def _keep_narrowed(
        self, *, repository_id: str, receipt: HoldReceipt, candidates: Sequence[OwnedRegeneration[BaseModel]]
    ) -> None:
        for identifier, holders in _candidates_by_identifier(candidates=candidates).items():
            try:
                owned = _joined(candidates=holders)
                if owned is None:
                    continue
                previous_seq = receipt.previous_seqs.get(identifier)
                if previous_seq is None:
                    await self.narrowed.put(
                        repository_id=repository_id,
                        hold_seq=receipt.hold_seq,
                        identifier=identifier,
                        request=owned.request,
                    )
                elif owned.union is not None:
                    await self.narrowed.merge_put(
                        repository_id=repository_id,
                        previous_seq=previous_seq,
                        hold_seq=receipt.hold_seq,
                        identifier=identifier,
                        request=owned.request,
                        union=owned.union,
                    )
            # The item is held already, and a missing entry only widens its release.
            except Exception:
                log.warning(
                    "Could not keep the narrowed held request; its release dispatches the held item unnarrowed",
                    repository_id=repository_id,
                    hold_seq=receipt.hold_seq,
                    identifier=identifier,
                    exc_info=True,
                )


def _combined(*, candidates: Sequence[OwnedRegeneration[BaseModel]]) -> HeldRegeneration:
    combined = HeldRegeneration()
    for candidate in candidates:
        combined, _ = combined.with_hold(held=candidate.held)
    return combined


def _candidates_by_identifier(
    *, candidates: Sequence[OwnedRegeneration[BaseModel]]
) -> dict[str, list[OwnedRegeneration[BaseModel]]]:
    by_identifier: dict[str, list[OwnedRegeneration[BaseModel]]] = {}
    for candidate in candidates:
        held = candidate.held
        identifiers = [item.identifier for item in (*held.artifact_definitions, *held.generator_definitions)]
        identifiers.extend(attribute.identifier for attribute in held.python_attributes)
        for identifier in identifiers:
            by_identifier.setdefault(identifier, []).append(candidate)
    return by_identifier


def _joined(*, candidates: Sequence[OwnedRegeneration[BaseModel]]) -> OwnedRegeneration[BaseModel] | None:
    """Join the requests of the candidates that hold one item, or return None when they cannot be joined."""
    joined, *others = candidates
    for candidate in others:
        if candidate.union is None:
            return None
        joined = replace(candidate, request=candidate.union(joined.request, candidate.request))
    return joined
