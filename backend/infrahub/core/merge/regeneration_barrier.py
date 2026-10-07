from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from pydantic import BaseModel

from infrahub.git.writeback.constants import BARRIER_STATE_READ_DELAYS_SECONDS, BARRIER_STATE_READ_RETRIES
from infrahub.git.writeback.models import HeldRegeneration
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from infrahub.git.writeback.models import HoldReceipt
    from infrahub.git.writeback.ports import DeliveryStatePort
    from infrahub.services.adapters.cache import InfrahubCache

log = get_logger()


@dataclass(frozen=True)
class OwnedRegeneration[RequestT: BaseModel]:
    """One candidate of the barrier: what to hold, the repository that owns it, and the request to dispatch."""

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

    It never raises: when the delivery state cannot be read after the retries, it admits every candidate.
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
        delays = iter(BARRIER_STATE_READ_DELAYS_SECONDS[:BARRIER_STATE_READ_RETRIES])
        while True:
            try:
                return await self._partition(candidates=candidates, releasing=releasing)
            # Nothing retries the flows that consult the barrier, so a raise would drop their regeneration.
            except Exception:
                delay = next(delays, None)
                if delay is None:
                    log.exception(
                        "Could not read the delivery state; dispatching every candidate without a hold",
                        branch=branch,
                        repository_ids=sorted(
                            {candidate.repository_id for candidate in candidates if candidate.repository_id is not None}
                        ),
                    )
                    return list(candidates)
                log.warning("Could not read the delivery state; reading it again", branch=branch, exc_info=True)
                await self.sleep(delay)

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
        try:
            for identifier, owned in _narrowed_by_identifier(candidates=candidates).items():
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
        # The items are held already, and a missing entry only widens their release.
        except Exception:
            log.warning(
                "Could not keep the narrowed held requests; their release dispatches the held items unnarrowed",
                repository_id=repository_id,
                hold_seq=receipt.hold_seq,
                exc_info=True,
            )


def _combined(*, candidates: Sequence[OwnedRegeneration[BaseModel]]) -> HeldRegeneration:
    combined = HeldRegeneration()
    for candidate in candidates:
        combined, _ = combined.with_hold(held=candidate.held)
    return combined


def _narrowed_by_identifier(
    *, candidates: Sequence[OwnedRegeneration[BaseModel]]
) -> dict[str, OwnedRegeneration[BaseModel]]:
    """Join the requests of the candidates that hold the same item; an item whose requests cannot be joined keeps none."""
    narrowed: dict[str, OwnedRegeneration[BaseModel] | None] = {}
    for candidate in candidates:
        held = candidate.held
        identifiers = [item.identifier for item in (*held.artifact_definitions, *held.generator_definitions)]
        identifiers.extend(attribute.identifier for attribute in held.python_attributes)
        for identifier in identifiers:
            if identifier not in narrowed:
                narrowed[identifier] = candidate
                continue
            earlier = narrowed[identifier]
            narrowed[identifier] = (
                None
                if earlier is None or candidate.union is None
                else replace(candidate, request=candidate.union(earlier.request, candidate.request))
            )
    return {identifier: owned for identifier, owned in narrowed.items() if owned is not None}
