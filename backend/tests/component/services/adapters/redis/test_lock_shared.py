import pytest

from infrahub import config
from infrahub.lock import InfrahubLockRegistry
from tests.helpers.shared_lock_scenarios import (
    exclusive_waits_for_the_shared_holder_of_another_worker,
    shared_waits_while_another_worker_holds_it_exclusively,
    the_record_of_a_holder_that_stopped_renewing_it_expires,
)


@pytest.fixture
def redis_driver(redis: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")


async def test_an_exclusive_request_waits_for_the_shared_holder_of_another_worker(redis_driver: None) -> None:
    await exclusive_waits_for_the_shared_holder_of_another_worker(
        worker_a=InfrahubLockRegistry(local_only=False), worker_b=InfrahubLockRegistry(local_only=False)
    )


async def test_a_shared_request_waits_while_another_worker_holds_it_exclusively(redis_driver: None) -> None:
    await shared_waits_while_another_worker_holds_it_exclusively(
        worker_a=InfrahubLockRegistry(local_only=False), worker_b=InfrahubLockRegistry(local_only=False)
    )


async def test_the_record_of_a_holder_that_stopped_renewing_it_expires(redis_driver: None) -> None:
    await the_record_of_a_holder_that_stopped_renewing_it_expires(worker=InfrahubLockRegistry(local_only=False))
