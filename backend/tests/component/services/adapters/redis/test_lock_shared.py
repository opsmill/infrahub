from collections.abc import AsyncGenerator

import pytest

from infrahub import config
from infrahub.lock import InfrahubLockRegistry, get_shared_holders_key
from infrahub.redis_connection import build_redis_connection
from tests.helpers.shared_lock_scenarios import (
    exclusive_ignores_the_holders_of_a_lock_whose_name_extends_its_own,
    exclusive_waits_for_the_shared_holder_of_another_worker,
    shared_waits_while_another_worker_holds_it_exclusively,
    the_record_of_a_holder_that_stopped_renewing_it_expires,
    unique_lock_name,
)


@pytest.fixture
def redis_driver(redis: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")


DOCUMENTED_ACL_USER = "infrahub-documented-acl"
DOCUMENTED_ACL_PASSWORD = "documented-acl-password"
# The rules the production deployment guide gives the cache user, so a command outside them fails here first.
DOCUMENTED_ACL_RULES = (
    "on",
    f">{DOCUMENTED_ACL_PASSWORD}",
    "~*",
    "allchannels",
    "+@read",
    "+@write",
    "+@connection",
    "+@scripting",
    "+@transaction",
    "+@pubsub",
    "-@dangerous",
)


@pytest.fixture
async def documented_acl_user(redis_driver: None, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    admin = build_redis_connection(config.SETTINGS.cache)
    await admin.execute_command("ACL", "SETUSER", DOCUMENTED_ACL_USER, *DOCUMENTED_ACL_RULES)
    monkeypatch.setattr(config.SETTINGS.cache, "username", DOCUMENTED_ACL_USER)
    monkeypatch.setattr(config.SETTINGS.cache, "password", DOCUMENTED_ACL_PASSWORD)
    yield
    await admin.execute_command("ACL", "DELUSER", DOCUMENTED_ACL_USER)
    await admin.aclose()


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


async def test_an_exclusive_request_waits_for_the_holder_of_a_lock_named_with_glob_characters(
    redis_driver: None,
) -> None:
    await exclusive_waits_for_the_shared_holder_of_another_worker(
        worker_a=InfrahubLockRegistry(local_only=False),
        worker_b=InfrahubLockRegistry(local_only=False),
        name=f"{unique_lock_name()}.[a-z]*?\\",
    )


async def test_an_exclusive_request_ignores_the_holders_of_a_lock_whose_name_extends_its_own(
    redis_driver: None,
) -> None:
    await exclusive_ignores_the_holders_of_a_lock_whose_name_extends_its_own(
        worker_a=InfrahubLockRegistry(local_only=False), worker_b=InfrahubLockRegistry(local_only=False)
    )


async def test_the_set_of_holder_ids_drops_an_expired_holder_and_is_deleted_once_empty(redis_driver: None) -> None:
    registry = InfrahubLockRegistry(local_only=False)
    connection = registry.connection
    assert connection is not None
    key = get_shared_holders_key(name=unique_lock_name())
    await registry.shared_holder_store.add(key=key, holder="dead-holder", token="token", ttl_seconds=1)
    await registry.shared_holder_store.add(key=key, holder="live-holder", token="token", ttl_seconds=60)
    await connection.delete(f"{key}.dead-holder")

    assert await registry.shared_holder_store.has_holders(key=key)
    assert await connection.smembers(key) == {b"live-holder"}

    await registry.shared_holder_store.remove(key=key, holder="live-holder")

    assert not await registry.shared_holder_store.has_holders(key=key)
    assert await connection.exists(key, f"{key}.live-holder") == 0


async def test_a_user_with_the_documented_acl_takes_and_waits_for_the_lock(documented_acl_user: None) -> None:
    await exclusive_waits_for_the_shared_holder_of_another_worker(
        worker_a=InfrahubLockRegistry(local_only=False), worker_b=InfrahubLockRegistry(local_only=False)
    )
    await the_record_of_a_holder_that_stopped_renewing_it_expires(worker=InfrahubLockRegistry(local_only=False))
