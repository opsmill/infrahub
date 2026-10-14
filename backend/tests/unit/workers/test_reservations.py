from __future__ import annotations

from uuid import uuid4

from infrahub.workers.reservations import CacheFlowRunReservations
from tests.adapters.cache import MemoryCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ExclusiveMemoryCache(MemoryCache):
    """In-memory cache whose keys expire on a manual clock.

    Setting a key only if it is absent fails while the key has not expired.
    """

    def __init__(self, clock: FakeClock | None = None) -> None:
        super().__init__()
        self.clock = clock or FakeClock()
        self.expires_at: dict[str, float] = {}

    async def get(self, key: str) -> str | None:
        if self.expires_at.get(key, float("inf")) <= self.clock():
            await self.delete(key=key)
        return await super().get(key=key)

    async def delete(self, key: str) -> None:
        self.expires_at.pop(key, None)
        await super().delete(key=key)

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        if not_exists and await self.get(key=key) is not None:
            return False
        if expires:
            self.expires_at[key] = self.clock() + expires
        else:
            self.expires_at.pop(key, None)
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


async def test_reservation_is_exclusive_between_owners() -> None:
    cache = ExclusiveMemoryCache()
    flow_run_id = uuid4()
    first = CacheFlowRunReservations(cache=cache, owner="worker-1", ttl=15)
    second = CacheFlowRunReservations(cache=cache, owner="worker-2", ttl=15)

    assert await first.reserve(flow_run_id=flow_run_id) is True
    assert await second.reserve(flow_run_id=flow_run_id) is False


async def test_owner_can_reserve_a_run_it_already_holds() -> None:
    cache = ExclusiveMemoryCache()
    flow_run_id = uuid4()
    reservations = CacheFlowRunReservations(cache=cache, owner="worker-1", ttl=15)
    await reservations.reserve(flow_run_id=flow_run_id)

    assert await reservations.reserve(flow_run_id=flow_run_id) is True


async def test_release_leaves_a_reservation_held_by_another_owner() -> None:
    cache = ExclusiveMemoryCache()
    flow_run_id = uuid4()
    first = CacheFlowRunReservations(cache=cache, owner="worker-1", ttl=15)
    second = CacheFlowRunReservations(cache=cache, owner="worker-2", ttl=15)
    await first.reserve(flow_run_id=flow_run_id)

    await second.release(flow_run_id=flow_run_id)

    assert await second.reserve(flow_run_id=flow_run_id) is False
    await first.release(flow_run_id=flow_run_id)
    assert await second.reserve(flow_run_id=flow_run_id) is True


async def test_reservation_of_another_owner_can_be_taken_once_it_expires() -> None:
    clock = FakeClock()
    cache = ExclusiveMemoryCache(clock=clock)
    flow_run_id = uuid4()
    first = CacheFlowRunReservations(cache=cache, owner="worker-1", ttl=15)
    second = CacheFlowRunReservations(cache=cache, owner="worker-2", ttl=15)
    await first.reserve(flow_run_id=flow_run_id)

    clock.advance(15)

    assert await second.reserve(flow_run_id=flow_run_id) is True


async def test_reserving_a_run_already_held_restarts_its_expiry() -> None:
    clock = FakeClock()
    cache = ExclusiveMemoryCache(clock=clock)
    flow_run_id = uuid4()
    first = CacheFlowRunReservations(cache=cache, owner="worker-1", ttl=15)
    second = CacheFlowRunReservations(cache=cache, owner="worker-2", ttl=15)
    await first.reserve(flow_run_id=flow_run_id)
    clock.advance(14)

    assert await first.reserve(flow_run_id=flow_run_id) is True
    clock.advance(14)

    assert await second.reserve(flow_run_id=flow_run_id) is False
