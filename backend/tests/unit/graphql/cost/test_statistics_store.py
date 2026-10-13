from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from infrahub.core.constants import RelationshipDirection
from infrahub.graphql.cost.models import (
    HistogramBucket,
    KindStatistics,
    RelationshipSideStatistics,
    StatisticsPointer,
    TopNode,
)
from infrahub.graphql.cost.statistics_store import StatisticsSnapshotHolder, StatisticsStore
from tests.adapters.cache import CacheCall, RecordingCache

POINTER_KEY = "graphql_cost:statistics:current"
COMPUTED_AT = datetime(2026, 10, 8, 4, 17, 2, tzinfo=UTC)

PERSON = KindStatistics(
    kind="TestPerson",
    label_count=6,
    active_count=4,
    relationships=(
        RelationshipSideStatistics(
            identifier="person__car",
            direction=RelationshipDirection.BIDIR,
            nodes_with_peers=1,
            total_peers=2,
            peers_by_kind={"TestElectricCar": 2},
            histogram=(
                HistogramBucket(lower=0, upper=0, node_count=3, max=0),
                HistogramBucket(lower=2, upper=3, node_count=1, max=2),
            ),
            top_nodes=(TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e01", peers=2),),
        ),
    ),
)

ELECTRIC_CAR = KindStatistics(
    kind="TestElectricCar",
    label_count=2,
    active_count=2,
    relationships=(
        RelationshipSideStatistics(
            identifier="person__car",
            direction=RelationshipDirection.BIDIR,
            nodes_with_peers=2,
            total_peers=2,
            peers_by_kind={"TestPerson": 2},
            histogram=(HistogramBucket(lower=1, upper=1, node_count=2, max=1),),
            top_nodes=(
                TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e02", peers=1),
                TopNode(node_id="18a1f2c4-6a5e-4b0f-9a57-1f0d3c2b8e03", peers=1),
            ),
        ),
    ),
)


class StalePointerCache(RecordingCache):
    """Serves an older pointer on the first pointer read, as a reader sees it when a refresh runs right after."""

    def __init__(self, stale_pointer: str) -> None:
        super().__init__()
        self.stale_pointer: str | None = stale_pointer

    async def get(self, key: str) -> str | None:
        value = await super().get(key=key)
        if key == POINTER_KEY and self.stale_pointer is not None:
            value, self.stale_pointer = self.stale_pointer, None
        return value


class YieldingCache(RecordingCache):
    """Lets other tasks run while a batch of keys is read, as a network cache does."""

    async def get_values(self, keys: list[str]) -> list[str | None]:
        await asyncio.sleep(0)
        return await super().get_values(keys=keys)


async def _publish(store: StatisticsStore, kinds: list[KindStatistics], schema_hash: str = "9f3c0a7e") -> None:
    await store.publish(kinds=kinds, branch="main", computed_at=COMPUTED_AT, schema_hash=schema_hash)


async def test_first_publish_writes_every_kind_key_then_the_pointer() -> None:
    cache = RecordingCache()
    store = StatisticsStore(cache=cache)

    pointer = await store.publish(
        kinds=[PERSON, ELECTRIC_CAR], branch="main", computed_at=COMPUTED_AT, schema_hash="9f3c0a7e"
    )

    expected_pointer = StatisticsPointer(
        version=1,
        branch="main",
        computed_at=COMPUTED_AT,
        schema_hash="9f3c0a7e",
        kinds=("TestPerson", "TestElectricCar"),
    )
    assert pointer == expected_pointer
    assert cache.calls_of(operation="set") == [
        CacheCall(operation="set", keys=("graphql_cost:statistics:v1:kind:TestPerson",)),
        CacheCall(operation="set", keys=("graphql_cost:statistics:v1:kind:TestElectricCar",)),
        CacheCall(operation="set", keys=(POINTER_KEY,)),
    ]
    assert StatisticsPointer.from_json(cache.storage[POINTER_KEY]) == expected_pointer
    assert KindStatistics.from_json(cache.storage["graphql_cost:statistics:v1:kind:TestPerson"]) == PERSON
    assert KindStatistics.from_json(cache.storage["graphql_cost:statistics:v1:kind:TestElectricCar"]) == ELECTRIC_CAR


async def test_publish_deletes_the_keys_of_the_previous_version_after_moving_the_pointer() -> None:
    cache = RecordingCache()
    store = StatisticsStore(cache=cache)
    await _publish(store=store, kinds=[PERSON, ELECTRIC_CAR])
    cache.calls.clear()

    pointer = await store.publish(kinds=[PERSON], branch="main", computed_at=COMPUTED_AT, schema_hash="5b2d")

    assert pointer.version == 2
    assert sorted(cache.storage) == [POINTER_KEY, "graphql_cost:statistics:v2:kind:TestPerson"]
    writes_and_deletes = [call for call in cache.calls if call.operation in {"set", "delete"}]
    assert writes_and_deletes == [
        CacheCall(operation="set", keys=("graphql_cost:statistics:v2:kind:TestPerson",)),
        CacheCall(operation="set", keys=(POINTER_KEY,)),
        CacheCall(operation="delete", keys=("graphql_cost:statistics:v1:kind:TestPerson",)),
        CacheCall(operation="delete", keys=("graphql_cost:statistics:v1:kind:TestElectricCar",)),
    ]


async def test_publish_deletes_keys_left_under_the_version_it_writes() -> None:
    cache = RecordingCache()
    store = StatisticsStore(cache=cache)
    await _publish(store=store, kinds=[PERSON])
    cache.storage["graphql_cost:statistics:v2:kind:TestGazCar"] = ELECTRIC_CAR.to_json()
    cache.storage["graphql_cost:statistics:v2:kind:TestPerson"] = ELECTRIC_CAR.to_json()
    cache.calls.clear()

    await _publish(store=store, kinds=[PERSON])

    assert sorted(cache.storage) == [POINTER_KEY, "graphql_cost:statistics:v2:kind:TestPerson"]
    assert KindStatistics.from_json(cache.storage["graphql_cost:statistics:v2:kind:TestPerson"]) == PERSON
    writes_and_deletes = [call for call in cache.calls if call.operation in {"set", "delete"}]
    assert writes_and_deletes == [
        CacheCall(operation="delete", keys=("graphql_cost:statistics:v2:kind:TestGazCar",)),
        CacheCall(operation="delete", keys=("graphql_cost:statistics:v2:kind:TestPerson",)),
        CacheCall(operation="set", keys=("graphql_cost:statistics:v2:kind:TestPerson",)),
        CacheCall(operation="set", keys=(POINTER_KEY,)),
        CacheCall(operation="delete", keys=("graphql_cost:statistics:v1:kind:TestPerson",)),
    ]


async def test_holder_has_no_snapshot_without_a_pointer() -> None:
    cache = RecordingCache()
    holder = StatisticsSnapshotHolder()

    snapshot = await holder.get(store=StatisticsStore(cache=cache))

    assert snapshot is None
    assert cache.calls == [CacheCall(operation="get", keys=(POINTER_KEY,))]


async def test_holder_loads_a_version_once_and_reloads_when_the_pointer_moves() -> None:
    cache = RecordingCache()
    store = StatisticsStore(cache=cache)
    holder = StatisticsSnapshotHolder()
    await _publish(store=store, kinds=[PERSON, ELECTRIC_CAR])
    cache.calls.clear()

    first = await holder.get(store=store)
    second = await holder.get(store=store)

    assert first is not None
    assert second is first
    assert first.pointer.version == 1
    assert first.kinds == {"TestPerson": PERSON, "TestElectricCar": ELECTRIC_CAR}
    assert cache.calls_of(operation="get_values") == [
        CacheCall(
            operation="get_values",
            keys=(
                "graphql_cost:statistics:v1:kind:TestPerson",
                "graphql_cost:statistics:v1:kind:TestElectricCar",
            ),
        )
    ]

    await _publish(store=store, kinds=[PERSON], schema_hash="5b2d")
    cache.calls.clear()
    third = await holder.get(store=store)

    assert third is not None
    assert third.pointer.version == 2
    assert third.pointer.schema_hash == "5b2d"
    assert third.kinds == {"TestPerson": PERSON}
    assert cache.calls == [
        CacheCall(operation="get", keys=(POINTER_KEY,)),
        CacheCall(operation="get_values", keys=("graphql_cost:statistics:v2:kind:TestPerson",)),
    ]


async def test_holder_reloads_a_version_number_that_another_refresh_wrote() -> None:
    holder = StatisticsSnapshotHolder()
    first_store = StatisticsStore(cache=RecordingCache())
    await _publish(store=first_store, kinds=[PERSON, ELECTRIC_CAR])
    first = await holder.get(store=first_store)
    # An emptied cache starts again at version 1.
    second_cache = RecordingCache()
    second_store = StatisticsStore(cache=second_cache)
    await second_store.publish(
        kinds=[PERSON], branch="main", computed_at=datetime(2026, 10, 9, 4, 17, 2, tzinfo=UTC), schema_hash="5b2d"
    )
    second_cache.calls.clear()

    second = await holder.get(store=second_store)

    assert first is not None
    assert second is not None
    assert (first.pointer.version, second.pointer.version) == (1, 1)
    assert second.pointer.computed_at == datetime(2026, 10, 9, 4, 17, 2, tzinfo=UTC)
    assert second.kinds == {"TestPerson": PERSON}
    assert second_cache.calls == [
        CacheCall(operation="get", keys=(POINTER_KEY,)),
        CacheCall(operation="get_values", keys=("graphql_cost:statistics:v1:kind:TestPerson",)),
    ]


async def test_holder_loads_a_version_once_for_concurrent_requests() -> None:
    cache = YieldingCache()
    store = StatisticsStore(cache=cache)
    holder = StatisticsSnapshotHolder()
    await _publish(store=store, kinds=[PERSON, ELECTRIC_CAR])
    cache.calls.clear()

    snapshots = await asyncio.gather(*(holder.get(store=store) for _ in range(3)))

    assert [snapshot.pointer.version if snapshot else None for snapshot in snapshots] == [1, 1, 1]
    assert len(cache.calls_of(operation="get_values")) == 1


async def test_missing_kind_key_rereads_the_pointer_once_then_leaves_the_kind_without_statistics() -> None:
    cache = RecordingCache()
    store = StatisticsStore(cache=cache)
    holder = StatisticsSnapshotHolder()
    await _publish(store=store, kinds=[PERSON, ELECTRIC_CAR])
    del cache.storage["graphql_cost:statistics:v1:kind:TestElectricCar"]
    cache.calls.clear()

    snapshot = await holder.get(store=store)

    assert snapshot is not None
    assert snapshot.pointer.version == 1
    assert snapshot.kinds == {"TestPerson": PERSON}
    assert (
        snapshot.side(identifier="person__car", direction=RelationshipDirection.BIDIR, kind="TestElectricCar") is None
    )
    assert cache.calls_of(operation="get") == [
        CacheCall(operation="get", keys=(POINTER_KEY,)),
        CacheCall(operation="get", keys=(POINTER_KEY,)),
    ]
    assert len(cache.calls_of(operation="get_values")) == 1


async def test_missing_kind_key_loads_the_version_the_pointer_moved_to() -> None:
    publisher_cache = RecordingCache()
    publisher = StatisticsStore(cache=publisher_cache)
    await _publish(store=publisher, kinds=[PERSON, ELECTRIC_CAR])
    stale_pointer = publisher_cache.storage[POINTER_KEY]
    await _publish(store=publisher, kinds=[PERSON, ELECTRIC_CAR], schema_hash="5b2d")
    cache = StalePointerCache(stale_pointer=stale_pointer)
    cache.storage.update(publisher_cache.storage)
    holder = StatisticsSnapshotHolder()

    snapshot = await holder.get(store=StatisticsStore(cache=cache))

    assert snapshot is not None
    assert snapshot.pointer.version == 2
    assert snapshot.kinds == {"TestPerson": PERSON, "TestElectricCar": ELECTRIC_CAR}
    assert cache.calls == [
        CacheCall(operation="get", keys=(POINTER_KEY,)),
        CacheCall(
            operation="get_values",
            keys=(
                "graphql_cost:statistics:v1:kind:TestPerson",
                "graphql_cost:statistics:v1:kind:TestElectricCar",
            ),
        ),
        CacheCall(operation="get", keys=(POINTER_KEY,)),
        CacheCall(
            operation="get_values",
            keys=(
                "graphql_cost:statistics:v2:kind:TestPerson",
                "graphql_cost:statistics:v2:kind:TestElectricCar",
            ),
        ),
    ]
