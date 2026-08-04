"""Read this process's CPU and memory allocation and aggregate it across a fleet.

Each process reports the logical CPU count it can see, the CPU quota enforced on
it by its container control group (``None`` when nothing is enforced), and its
memory capacity and free memory. The process's own control group is resolved
from ``/proc/self/cgroup`` and every level up to the root is consulted, because
a limit may be enforced on an ancestor — under a private cgroup namespace (the
modern container default) that path collapses to the apparent root, while a host
namespace or a systemd service exposes the full hierarchy. cgroup v2 is read
first, then v1; a host with neither — a developer laptop, an unusual mount —
falls back to the whole-host figures from psutil and reports no CPU quota.
Limits above a private namespace root (for example a pod-level limit when the
container itself has none) are invisible from inside and cannot be reported.

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
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING

import psutil
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable

CGROUP_ROOT = Path("/sys/fs/cgroup")
PROC_SELF_CGROUP = Path("/proc/self/cgroup")

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

    @classmethod
    def failed(cls) -> WorkerResourceReading:
        """The reading written when a process's self-read failed outright.

        It carries no figures and a host stand-in, so it is recognisable as
        failed (see ``is_failed``) and is dropped from aggregation rather than
        summed or used for host dedup.
        """
        return cls(host="unknown")

    @property
    def is_failed(self) -> bool:
        """Whether this reading is a failed self-read rather than a contribution.

        A healthy host always reports at least its logical CPU count and memory
        capacity; only a read that failed after its retries carries every figure
        as ``None``. Derived from the field set so a new figure is covered
        automatically.
        """
        return all(value is None for value in self.model_dump(exclude={"host"}).values())


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


def _own_cgroup_dirs(cgroup_root: Path, proc_cgroup: Path) -> list[Path]:
    """Return this process's cgroup directory and its ancestors, leaf first.

    Under a private cgroup namespace (the modern container default) the process
    sits at the apparent root and the list collapses to ``[cgroup_root]``. Without
    one — an older runtime, an explicit host namespace, a systemd service — the
    ``0::<path>`` line of the proc file locates the real cgroup, and every level
    up to the root is returned because a limit may be enforced on any ancestor.
    An unreadable proc file, a missing v2 line, or a path that does not exist
    under the root all fall back to ``[cgroup_root]``, preserving the plain read.
    """
    content = _read_text_file(proc_cgroup)
    if content is None:
        return [cgroup_root]
    for line in content.splitlines():
        if not line.startswith("0::"):
            continue
        relative = line[3:].strip().lstrip("/")
        if not relative or ".." in relative.split("/"):
            return [cgroup_root]
        leaf = cgroup_root / relative
        if not leaf.is_dir():
            return [cgroup_root]
        dirs = [leaf]
        for parent in leaf.parents:
            dirs.append(parent)
            if parent == cgroup_root:
                break
        return dirs
    return [cgroup_root]


def _parse_cpu_max(line: str) -> int | None:
    """Parse one cgroup v2 ``cpu.max`` line ("<quota> <period>", "max" = unbounded)."""
    parts = line.split()
    if not parts or parts[0] == "max":
        return None
    try:
        quota = int(parts[0])
        period = int(parts[1]) if len(parts) > 1 else _DEFAULT_CPU_PERIOD_US
    except ValueError:
        return None
    return _quota_to_cores(quota=quota, period=period)


def _read_cgroup_cpu_quota(cgroup_dirs: list[Path]) -> int | None:
    """Return the enforced CPU limit in whole cores, or ``None`` when unbounded.

    Every level of the process's cgroup path may carry a v2 ``cpu.max``; the
    effective limit is the most restrictive one. A hierarchy with no readable
    ``cpu.max`` at any level is treated as cgroup v1, whose ``cpu.cfs_quota_us``
    / ``cpu.cfs_period_us`` pair (quota ``-1`` = unbounded) lives at the
    controller mount root inside a container.
    """
    v2_lines = [line for directory in cgroup_dirs if (line := _read_text_file(directory / "cpu.max")) is not None]
    if v2_lines:
        cores = [value for line in v2_lines if (value := _parse_cpu_max(line)) is not None]
        return min(cores) if cores else None

    root = cgroup_dirs[-1]
    quota = _read_int_file(root / "cpu" / "cpu.cfs_quota_us")
    period = _read_int_file(root / "cpu" / "cpu.cfs_period_us")
    if quota is None or period is None:
        return None
    return _quota_to_cores(quota=quota, period=period)


def _read_cgroup_memory_limit(cgroup_dirs: list[Path]) -> tuple[int | None, Path | None]:
    """Return ``(limit_bytes, current_usage_path)`` for the memory control group.

    Every level of the process's cgroup path may carry a v2 ``memory.max``
    ("max" = unbounded); the effective limit is the smallest, and usage is read
    from that same level — an ancestor limit is shared with siblings, so free
    memory within it is the limit minus the whole subtree's usage. A hierarchy
    with no readable ``memory.max`` at any level is treated as cgroup v1, whose
    ``memory.limit_in_bytes`` reports a near-``INT64_MAX`` sentinel when
    unbounded. ``(None, None)`` means no limit is enforced anywhere.
    """
    limits: list[tuple[int, Path]] = []
    v2_seen = False
    for directory in cgroup_dirs:
        raw = _read_text_file(directory / "memory.max")
        if raw is None:
            continue
        v2_seen = True
        if raw == "max":
            continue
        try:
            limits.append((int(raw), directory))
        except ValueError:
            continue
    if v2_seen:
        if not limits:
            return None, None
        limit, directory = min(limits, key=itemgetter(0))
        return limit, directory / "memory.current"

    root = cgroup_dirs[-1]
    v1_limit = _read_int_file(root / "memory" / "memory.limit_in_bytes")
    if v1_limit is None or v1_limit >= _CGROUP_MEMORY_UNLIMITED_THRESHOLD:
        return None, None
    return v1_limit, root / "memory" / "memory.usage_in_bytes"


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

    def __init__(self, cgroup_root: Path = CGROUP_ROOT, proc_cgroup: Path = PROC_SELF_CGROUP) -> None:
        self._cgroup_root = cgroup_root
        self._proc_cgroup = proc_cgroup
        self._static: _StaticResources | None = None

    def _read_static(self) -> _StaticResources:
        cgroup_dirs = _own_cgroup_dirs(cgroup_root=self._cgroup_root, proc_cgroup=self._proc_cgroup)
        memory_limit, memory_current_path = _read_cgroup_memory_limit(cgroup_dirs)
        memory_total = memory_limit if memory_limit is not None else _host_memory_total()
        return _StaticResources(
            host=socket.gethostname(),
            processor_available=psutil.cpu_count(logical=True),
            processor_assigned=_read_cgroup_cpu_quota(cgroup_dirs),
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
        if reading.is_failed:
            continue
        by_host.setdefault(reading.host, reading)

    deduped = list(by_host.values())
    return ResourceAggregate(
        processor_available=_sum_over_hosts([reading.processor_available for reading in deduped]),
        processor_assigned=_sum_over_hosts([reading.processor_assigned for reading in deduped]),
        memory_total=_sum_over_hosts([reading.memory_total for reading in deduped]),
        memory_available=_sum_over_hosts([reading.memory_available for reading in deduped]),
    )
