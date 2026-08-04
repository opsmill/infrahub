"""Read this process's CPU and memory allocation and aggregate it across a fleet.

Each process reports the logical CPU count it can see, the CPU quota enforced on
it by its container control group (``None`` when nothing is enforced), and its
memory capacity and free memory. The container control group is consulted first
(cgroup v2, then v1); a host without one — a developer laptop, an unusual mount —
falls back to the whole-host figures from psutil and reports no CPU quota.

The values that cannot change for the lifetime of a process (the host identifier,
the logical CPU count, the enforced CPU quota and the memory capacity) are read
once and cached; only free memory is re-read, since it moves with usage.

Aggregation collapses the several processes of one container into a single
contribution (they share a host and a control group, so their readings are
identical) and sums across distinct hosts.
"""

from __future__ import annotations

import math
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import psutil
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable

CGROUP_ROOT = Path("/sys/fs/cgroup")

# The default CPU period the kernel uses when a cgroup v2 ``cpu.max`` line omits it.
_DEFAULT_CPU_PERIOD_US = 100000

# cgroup v1 reports a value near the signed-64-bit maximum for an unlimited memory
# limit; anything this large means "no limit", not a real capacity. The threshold
# sits far above any real memory size yet below every kernel/page-size sentinel.
_CGROUP_MEMORY_UNLIMITED_THRESHOLD = 2**62

# Everything a resource self-read can raise: I/O failures (hostname lookup, the
# pseudo-filesystem reads behind psutil) and psutil's own error family. Parse
# errors never escape — every cgroup value is guarded where it is read — so a
# caller retrying these is retrying transient conditions, not bugs.
RESOURCE_READ_FAILURES = (OSError, psutil.Error)


class WorkerResourceReading(BaseModel):
    """One process's view of its own CPU and memory allocation.

    Transits the heartbeat cache as JSON. ``host`` is the container identifier
    used to collapse the several processes of one container into a single
    contribution; it is a dedup key only and is never emitted in the payload.
    """

    host: str
    processor_available: int | None = None
    processor_assigned: int | None = None
    memory_total: int | None = None
    memory_available: int | None = None


@dataclass(frozen=True)
class ResourceAggregate:
    """The four resource figures summed over the distinct hosts of a component."""

    processor_available: int | None = None
    processor_assigned: int | None = None
    memory_total: int | None = None
    memory_available: int | None = None


@dataclass(frozen=True)
class _StaticResources:
    """The per-process facts that never change while the process lives."""

    host: str
    processor_available: int | None
    processor_assigned: int | None
    memory_total: int | None
    memory_limit: int | None
    memory_current_path: Path | None


def _read_text_file(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except (OSError, ValueError):
        return None


def _read_int_file(path: Path) -> int | None:
    content = _read_text_file(path)
    if content is None:
        return None
    try:
        return int(content)
    except ValueError:
        return None


def _quota_to_cores(quota: int, period: int) -> int | None:
    """Convert a CPU-time quota/period pair to whole cores, rounding up.

    A fractional quota rounds up to the next whole core so an audit never
    understates the enforced cap. A non-positive quota or period means unbounded.
    """
    if quota <= 0 or period <= 0:
        return None
    return math.ceil(quota / period)


def _read_cgroup_cpu_quota(cgroup_root: Path) -> int | None:
    """Return the enforced CPU limit in whole cores, or ``None`` when unbounded.

    cgroup v2 ``cpu.max`` ("<quota> <period>", or "max <period>" when unbounded)
    is read first; a host on cgroup v1 uses the ``cpu.cfs_quota_us`` /
    ``cpu.cfs_period_us`` pair, where a quota of ``-1`` means unbounded.
    """
    v2_line = _read_text_file(cgroup_root / "cpu.max")
    if v2_line is not None:
        parts = v2_line.split()
        if not parts or parts[0] == "max":
            return None
        try:
            v2_quota = int(parts[0])
            v2_period = int(parts[1]) if len(parts) > 1 else _DEFAULT_CPU_PERIOD_US
        except ValueError:
            return None
        return _quota_to_cores(quota=v2_quota, period=v2_period)

    quota = _read_int_file(cgroup_root / "cpu" / "cpu.cfs_quota_us")
    period = _read_int_file(cgroup_root / "cpu" / "cpu.cfs_period_us")
    if quota is None or period is None:
        return None
    return _quota_to_cores(quota=quota, period=period)


def _read_cgroup_memory_limit(cgroup_root: Path) -> tuple[int | None, Path | None]:
    """Return ``(limit_bytes, current_usage_path)`` for the memory control group.

    ``limit_bytes`` is ``None`` when memory is unbounded or no control group is
    readable; ``current_usage_path`` points at the file holding current usage so
    free memory can be recomputed cheaply on each heartbeat. cgroup v2
    ``memory.max`` ("max" when unbounded) takes precedence over the v1
    ``memory.limit_in_bytes`` value, which reports a near-``INT64_MAX`` sentinel
    when unbounded.
    """
    v2_max = _read_text_file(cgroup_root / "memory.max")
    if v2_max is not None:
        if v2_max == "max":
            return None, None
        try:
            v2_limit = int(v2_max)
        except ValueError:
            return None, None
        return v2_limit, cgroup_root / "memory.current"

    limit = _read_int_file(cgroup_root / "memory" / "memory.limit_in_bytes")
    if limit is None or limit >= _CGROUP_MEMORY_UNLIMITED_THRESHOLD:
        return None, None
    return limit, cgroup_root / "memory" / "memory.usage_in_bytes"


def _host_memory_total() -> int | None:
    return int(psutil.virtual_memory().total)


def _host_memory_available() -> int | None:
    return int(psutil.virtual_memory().available)


class ProcessResources:
    """Read and cache this process's static resource facts, refreshing free memory.

    The host identifier, logical CPU count, enforced CPU quota and memory capacity
    are fixed for the lifetime of a process and are read once; each read re-reads
    only free memory, which moves with usage.
    """

    def __init__(self, cgroup_root: Path = CGROUP_ROOT) -> None:
        self._cgroup_root = cgroup_root
        self._static: _StaticResources | None = None

    def _read_static(self) -> _StaticResources:
        memory_limit, memory_current_path = _read_cgroup_memory_limit(self._cgroup_root)
        memory_total = memory_limit if memory_limit is not None else _host_memory_total()
        return _StaticResources(
            host=socket.gethostname(),
            processor_available=psutil.cpu_count(logical=True),
            processor_assigned=_read_cgroup_cpu_quota(self._cgroup_root),
            memory_total=memory_total,
            memory_limit=memory_limit,
            memory_current_path=memory_current_path,
        )

    def _read_memory_available(self, static: _StaticResources) -> int | None:
        if static.memory_limit is not None and static.memory_current_path is not None:
            current = _read_int_file(static.memory_current_path)
            if current is None:
                return None
            return static.memory_limit - current
        return _host_memory_available()

    def read(self) -> WorkerResourceReading:
        if self._static is None:
            self._static = self._read_static()
        return WorkerResourceReading(
            host=self._static.host,
            processor_available=self._static.processor_available,
            processor_assigned=self._static.processor_assigned,
            memory_total=self._static.memory_total,
            memory_available=self._read_memory_available(self._static),
        )


def _sum_over_hosts(values: list[int | None]) -> int | None:
    """Sum the per-host values for one field, or ``None`` when it cannot be summed.

    No values (no host contributed) and any ``None`` value (a host that is
    genuinely unbounded, so the fleet has no finite total) both collapse to
    ``None``. Otherwise the finite per-host values are summed.
    """
    if not values or any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _is_failed_reading(reading: WorkerResourceReading) -> bool:
    """A reading carrying a host but no figure at all is a failed self-read.

    A healthy host always reports its logical CPU count and memory capacity; only a
    read that failed after its retries carries every figure as ``None``. Such a
    reading is not a real contribution and must not null the fleet.
    """
    return (
        reading.processor_available is None
        and reading.processor_assigned is None
        and reading.memory_total is None
        and reading.memory_available is None
    )


def aggregate(readings: Iterable[WorkerResourceReading]) -> ResourceAggregate:
    """Collapse per-process readings into one figure per field for a component.

    Readings are deduplicated by host (processes on one host report identical
    values) and each field is then summed across the distinct hosts. A host whose
    read failed (every figure ``None``) is skipped, and a host that never reported
    is simply absent, so both undercount the sum — a gap the separately-tracked
    worker count exposes — rather than nulling the whole fleet.
    """
    by_host: dict[str, WorkerResourceReading] = {}
    for reading in readings:
        if _is_failed_reading(reading):
            continue
        by_host.setdefault(reading.host, reading)

    deduped = list(by_host.values())
    return ResourceAggregate(
        processor_available=_sum_over_hosts([reading.processor_available for reading in deduped]),
        processor_assigned=_sum_over_hosts([reading.processor_assigned for reading in deduped]),
        memory_total=_sum_over_hosts([reading.memory_total for reading in deduped]),
        memory_available=_sum_over_hosts([reading.memory_available for reading in deduped]),
    )
