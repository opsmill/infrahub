from collections.abc import AsyncGenerator

import pytest

from infrahub import config
from infrahub.lock import InfrahubLockRegistry
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.nats import NATSCache
from tests.helpers.shared_lock_scenarios import (
    exclusive_waits_for_the_shared_holder_of_another_worker,
    shared_waits_while_another_worker_holds_it_exclusively,
    the_record_of_a_holder_that_stopped_renewing_it_expires,
)


@pytest.fixture
async def nats_services(nats: dict[int, int] | None) -> AsyncGenerator[list[InfrahubServices]]:
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")
    services = [await InfrahubServices.new(cache=await NATSCache.new()) for _ in range(2)]
    yield services
    for service in services:
        await service.cache.close_connection()


async def test_an_exclusive_request_waits_for_the_shared_holder_of_another_worker(
    nats_services: list[InfrahubServices],
) -> None:
    await exclusive_waits_for_the_shared_holder_of_another_worker(
        worker_a=InfrahubLockRegistry(local_only=False, service=nats_services[0]),
        worker_b=InfrahubLockRegistry(local_only=False, service=nats_services[1]),
    )


async def test_a_shared_request_waits_while_another_worker_holds_it_exclusively(
    nats_services: list[InfrahubServices],
) -> None:
    await shared_waits_while_another_worker_holds_it_exclusively(
        worker_a=InfrahubLockRegistry(local_only=False, service=nats_services[0]),
        worker_b=InfrahubLockRegistry(local_only=False, service=nats_services[1]),
    )


async def test_the_record_of_a_holder_that_stopped_renewing_it_expires(nats_services: list[InfrahubServices]) -> None:
    await the_record_of_a_holder_that_stopped_renewing_it_expires(
        worker=InfrahubLockRegistry(local_only=False, service=nats_services[0])
    )
