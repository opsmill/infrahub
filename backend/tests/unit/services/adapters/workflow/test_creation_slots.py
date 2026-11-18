import asyncio

from prefect.client.orchestration import PrefectClient

from infrahub.services.adapters.workflow.creation_slots import RunCreationSlots

CAPACITY = 3
CREATIONS_PER_CLIENT = 10


def build_client() -> PrefectClient:
    return PrefectClient(api="http://127.0.0.1:1/api")


async def peak_concurrent_creations(slots: RunCreationSlots, clients: list[PrefectClient | None]) -> int:
    active = 0
    peak = 0

    async def create(client: PrefectClient | None) -> None:
        nonlocal active, peak
        async with slots.slot(client=client):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1

    await asyncio.gather(*(create(client=client) for client in clients for _ in range(CREATIONS_PER_CLIENT)))
    return peak


async def test_creations_through_one_client_never_exceed_the_capacity() -> None:
    slots = RunCreationSlots(capacity=CAPACITY)

    assert await peak_concurrent_creations(slots=slots, clients=[build_client()]) == CAPACITY


async def test_each_client_has_its_own_slots() -> None:
    slots = RunCreationSlots(capacity=CAPACITY)

    assert await peak_concurrent_creations(slots=slots, clients=[build_client(), build_client()]) == 2 * CAPACITY


async def test_creations_without_a_shared_client_are_not_bounded() -> None:
    slots = RunCreationSlots(capacity=CAPACITY)

    assert await peak_concurrent_creations(slots=slots, clients=[None]) == CREATIONS_PER_CLIENT
