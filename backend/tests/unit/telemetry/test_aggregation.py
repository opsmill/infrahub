"""Unit tests for the fleet resource aggregation.

Aggregation deduplicates readings by host (the several processes of one container
report identical values), then sums each field across the distinct hosts. A field
is ``None`` (unknown or unbounded) when no reading carried it or when any
contributing host reports it as ``None`` because it is genuinely unbounded — a
fleet that includes an unbounded node has no finite total. Only the four resource
figures are returned; the worker count is tracked separately by the caller.
"""

from __future__ import annotations

from infrahub.telemetry.resources import ResourceAggregate, WorkerResourceReading, aggregate


def _reading(
    host: str,
    *,
    processor_available: int | None = None,
    processor_assigned: int | None = None,
    memory_total: int | None = None,
    memory_available: int | None = None,
) -> WorkerResourceReading:
    return WorkerResourceReading(
        host=host,
        processor_available=processor_available,
        processor_assigned=processor_assigned,
        memory_total=memory_total,
        memory_available=memory_available,
    )


def test_readings_on_one_host_are_deduplicated() -> None:
    readings = [_reading("c1", processor_available=4, memory_total=8, memory_available=6) for _ in range(8)]

    result = aggregate(readings)

    assert result == ResourceAggregate(
        processor_available=4,
        processor_assigned=None,
        memory_total=8,
        memory_available=6,
    )


def test_distinct_hosts_are_summed() -> None:
    readings = [
        _reading("w1", processor_available=4, memory_total=8, memory_available=6),
        _reading("w2", processor_available=4, memory_total=8, memory_available=5),
    ]

    result = aggregate(readings)

    assert result == ResourceAggregate(
        processor_available=8,
        processor_assigned=None,
        memory_total=16,
        memory_available=11,
    )


def test_undercount_sums_only_the_reporting_hosts() -> None:
    # Three worker processes ran, but only two distinct hosts wrote a reading; the
    # aggregate sums those two. The caller's worker count (tracked separately)
    # still reflects all three, so the gap is detectable.
    readings = [
        _reading("w1", processor_available=4),
        _reading("w2", processor_available=4),
    ]

    result = aggregate(readings)

    assert result.processor_available == 8


def test_field_is_none_when_no_reading_carried_it() -> None:
    readings = [
        _reading("w1", processor_available=4),
        _reading("w2", processor_available=4),
    ]

    result = aggregate(readings)

    assert result.processor_assigned is None
    assert result.memory_total is None
    assert result.memory_available is None


def test_field_is_none_when_any_contributing_host_is_unbounded() -> None:
    # Two healthy hosts (each reporting its cores and memory): one has an enforced
    # quota, the other is unbounded (``processor_assigned`` is None). A fleet that
    # contains an unbounded node has no finite assignment.
    readings = [
        _reading("w1", processor_available=4, memory_total=8, memory_available=6, processor_assigned=4),
        _reading("w2", processor_available=4, memory_total=8, memory_available=6, processor_assigned=None),
    ]

    result = aggregate(readings)

    assert result.processor_assigned is None


def test_no_readings_yields_all_none() -> None:
    result = aggregate([])

    assert result == ResourceAggregate(
        processor_available=None,
        processor_assigned=None,
        memory_total=None,
        memory_available=None,
    )


def test_failed_read_is_dropped_and_does_not_null_the_fleet() -> None:
    # A host whose self-read failed writes a reading with no figure at all. It must
    # not collapse the whole fleet to None; the reporting hosts still sum (an
    # undercount the worker count exposes).
    readings = [
        _reading("w1", processor_available=4, memory_total=8, memory_available=6),
        _reading("w2", processor_available=4, memory_total=8, memory_available=6),
        _reading("w3"),
    ]

    result = aggregate(readings)

    assert result == ResourceAggregate(
        processor_available=8,
        processor_assigned=None,
        memory_total=16,
        memory_available=12,
    )


def test_healthy_reading_is_kept_over_a_failed_read_on_the_same_host() -> None:
    # A host with both a failed and a successful process must contribute its real
    # figures: the empty reading is dropped before deduplication.
    readings = [
        _reading("w1"),
        _reading("w1", processor_available=4, memory_total=8, memory_available=6),
    ]

    result = aggregate(readings)

    assert result.processor_available == 4
