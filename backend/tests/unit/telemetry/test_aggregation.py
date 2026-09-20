"""Unit tests for the fleet resource aggregation.

Aggregation deduplicates readings by host (the several processes of one container
report identical values), then sums each field across the distinct hosts. Three
of the four fields sum whatever hosts actually reported, so one host's read
failure on a single field only undercounts that field rather than nulling the
whole aggregate. ``processor_assigned`` is the exception: a contributing host's
``None`` there is a real value (no CPU limit enforced), and a fleet with one
unbounded host has no finite assignment, so that field alone nulls the whole
aggregate. Only the four resource figures are returned; the worker count is
not part of this aggregate.
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
    # Three worker processes ran, but only two distinct hosts wrote a reading;
    # the aggregate sums only those two, undercounting rather than nulling.
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


def test_one_hosts_field_failure_undercounts_only_that_field() -> None:
    # w2 is a genuine per-field read failure, not the fully-null failed() reading:
    # its memory_available read failed while processor_available and memory_total
    # succeeded. That field sums only the reporting host; the others still sum both.
    readings = [
        _reading("w1", processor_available=4, memory_total=8, memory_available=6),
        _reading("w2", processor_available=4, memory_total=8, memory_available=None),
    ]

    result = aggregate(readings)

    assert result.processor_available == 8
    assert result.memory_total == 16
    assert result.memory_available == 6


def test_processor_available_field_failure_undercounts_only_that_field() -> None:
    readings = [
        _reading("w1", processor_available=4, memory_total=8, memory_available=6),
        _reading("w2", processor_available=None, memory_total=8, memory_available=6),
    ]

    result = aggregate(readings)

    assert result.processor_available == 4
    assert result.memory_total == 16
    assert result.memory_available == 12


def test_processor_assigned_still_nulls_entirely_on_any_contributing_none() -> None:
    # Unlike the sum-of-reporters fields above, processor_assigned keeps the
    # all-or-null rule: one unbounded host still nulls the whole aggregate.
    readings = [
        _reading("w1", processor_available=4, memory_total=8, memory_available=6, processor_assigned=4),
        _reading("w2", processor_available=4, memory_total=8, memory_available=6, processor_assigned=None),
    ]

    result = aggregate(readings)

    assert result.processor_assigned is None
    assert result.processor_available == 8


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
