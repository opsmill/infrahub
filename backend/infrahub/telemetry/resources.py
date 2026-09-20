"""Read this process's CPU and memory allocation and aggregate it across a fleet.

Each process reports the logical CPUs it can use — the host's count capped by
the CPU quota its container control group enforces — that quota itself (``None``
when nothing is enforced), and its memory capacity and free memory. The cap is
the rule the JVM applies when it reports the database's processors, so the
figure means the same thing for every component. The process's own control
group is resolved from ``/proc/self/cgroup`` and every level up to the root is
consulted, because a limit may be enforced on an ancestor — under a private
cgroup namespace (the modern container default) that path collapses to the
apparent root, while a host namespace or a systemd service exposes the full
hierarchy. cgroup v2 is read first, then v1; a host with neither — a developer
laptop, an unusual mount — falls back to the whole-host figures from psutil and
reports no CPU quota. Limits above a private namespace root (for example a
pod-level limit when the container itself has none) are invisible from inside
and cannot be reported.

The host identifier, the resolved control-group path and the host's logical
CPU count cannot change without a container restart and are read once and
cached. The enforced CPU quota and the memory capacity can change while the
process runs — a live quota update, an in-place pod resize, a systemd unit
reload — so, like free memory, they are re-read on every call.

Aggregation collapses the several processes of one container into a single
contribution (they share a host and a control group, so their readings are
identical) and sums across distinct hosts.
"""

from __future__ import annotations

import logging
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

# Stdlib logging, not ``infrahub.log``: this module is also imported standalone
# (bind-mounted into a bare probe image with no ``infrahub`` distribution) by the
# real-kernel component tests, so it cannot depend on the package's own logging setup.
log = logging.getLogger(__name__)

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
class _ProcessIdentity:
    """The per-process facts that cannot change without a container restart."""

    host: str
    cgroup_dirs: list[Path]
    host_processor_count: int | None


@dataclass(frozen=True)
class _DynamicResources:
    """Resource figures that can change while the process runs and are re-read on every call."""

    processor_available: int | None
    processor_assigned: int | None
    memory_total: int | None
    memory_limit: int | None
    memory_available: int | None


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


class _CgroupLimitUnreadableError(Exception):
    """A cgroup limit file exists but its read failed, as opposed to the file being absent."""

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path: Path = path


def _read_cgroup_limit_file(path: Path) -> str | None:
    """Read one cgroup limit file, or ``None`` when nothing is configured at this level.

    A permission or I/O error is never mistaken for "no limit at this level" and
    cannot make an unenforced ancestor look effective.

    Raises:
        _CgroupLimitUnreadableError: The file exists but the read itself failed.

    """
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise _CgroupLimitUnreadableError(path) from exc


def _read_cgroup_int_limit(path: Path) -> int | None:
    content = _read_cgroup_limit_file(path)
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


def _usable_processors(host_count: int | None, quota_cores: int | None) -> int | None:
    """The logical CPUs the process can use: the host's count capped by the enforced quota.

    A quota above the host's count grants nothing extra, so the host figure stands;
    without a quota, or with no host figure to cap, whichever is known is returned.
    """
    if host_count is None:
        return quota_cores
    if quota_cores is None:
        return host_count
    return min(host_count, quota_cores)


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

    Raises:
        _CgroupLimitUnreadableError: A limit file exists but cannot be read, so
            the level must not be treated as absent and fallen through to a
            less restrictive one.

    """
    v2_lines = [
        line for directory in cgroup_dirs if (line := _read_cgroup_limit_file(directory / "cpu.max")) is not None
    ]
    if v2_lines:
        cores = [value for line in v2_lines if (value := _parse_cpu_max(line)) is not None]
        return min(cores) if cores else None

    root = cgroup_dirs[-1]
    quota = _read_cgroup_int_limit(root / "cpu" / "cpu.cfs_quota_us")
    period = _read_cgroup_int_limit(root / "cpu" / "cpu.cfs_period_us")
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

    Raises:
        _CgroupLimitUnreadableError: A limit file exists but cannot be read, so
            the level must not be treated as absent and fallen through to a
            less restrictive one.

    """
    limits: list[tuple[int, Path]] = []
    v2_seen = False
    for directory in cgroup_dirs:
        raw = _read_cgroup_limit_file(directory / "memory.max")
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
    v1_limit = _read_cgroup_int_limit(root / "memory" / "memory.limit_in_bytes")
    if v1_limit is None or v1_limit >= _CGROUP_MEMORY_UNLIMITED_THRESHOLD:
        return None, None
    return v1_limit, root / "memory" / "memory.usage_in_bytes"


def _host_memory_total() -> int | None:
    return int(psutil.virtual_memory().total)


def _host_memory_available() -> int | None:
    return int(psutil.virtual_memory().available)


# The limit and usage files worth reporting when explaining a read. The v2 names
# are looked for at every level of the process's cgroup path; the v1 names only
# at the controller mount root, which is where a container sees them.
_V2_EVIDENCE_FILES = ("cpu.max", "memory.max", "memory.current")
_V1_EVIDENCE_FILES = (
    "cpu/cpu.cfs_quota_us",
    "cpu/cpu.cfs_period_us",
    "memory/memory.limit_in_bytes",
    "memory/memory.usage_in_bytes",
)


@dataclass(frozen=True)
class CgroupLevel:
    """The limit files present at one level of the process's cgroup path."""

    path: str

    files: dict[str, str]
    """Contents of the limit files found here, keyed by file name; empty when the level carries none."""


@dataclass(frozen=True)
class ResourceDiagnostics:
    """A reading together with the evidence that produced it.

    Explains an environment whose reported figures look wrong: which cgroup the
    process resolved to, which limit files each level actually carried, and how
    the reported figures compare with the whole host's.
    """

    reading: WorkerResourceReading
    proc_cgroup: str | None
    """Raw contents of the proc cgroup file, or ``None`` when it is unreadable."""

    cgroup_v2_root: bool
    cgroup_v1_root: bool

    memory_limit: int | None
    """The enforced memory limit in bytes, or ``None`` when memory is unbounded."""

    levels: list[CgroupLevel]
    host_processor_available: int | None
    host_memory_total: int | None


class ProcessResources:
    """Read this process's resource facts, caching only what a container restart would change.

    The host identifier, the resolved control-group path and the host's logical
    CPU count are fixed for the lifetime of a process and are read once. The
    enforced CPU quota and memory capacity can be reconfigured while the process
    keeps running, so, like free memory, each read re-reads them.
    """

    def __init__(self, cgroup_root: Path = CGROUP_ROOT, proc_cgroup: Path = PROC_SELF_CGROUP) -> None:
        self._cgroup_root = cgroup_root
        self._proc_cgroup = proc_cgroup
        self._identity: _ProcessIdentity | None = None

    def _read_identity(self) -> _ProcessIdentity:
        return _ProcessIdentity(
            host=socket.gethostname(),
            cgroup_dirs=_own_cgroup_dirs(cgroup_root=self._cgroup_root, proc_cgroup=self._proc_cgroup),
            host_processor_count=psutil.cpu_count(logical=True),
        )

    def _process_identity(self) -> _ProcessIdentity:
        if self._identity is None:
            self._identity = self._read_identity()
        return self._identity

    def _read_memory_available(self, memory_limit: int | None, memory_current_path: Path | None) -> int | None:
        if memory_limit is not None and memory_current_path is not None:
            current = _read_int_file(memory_current_path)
            if current is None:
                return None
            return memory_limit - current
        return _host_memory_available()

    def _read_dynamic(self, identity: _ProcessIdentity) -> _DynamicResources:
        try:
            processor_assigned = _read_cgroup_cpu_quota(identity.cgroup_dirs)
            processor_available = _usable_processors(
                host_count=identity.host_processor_count, quota_cores=processor_assigned
            )
        except _CgroupLimitUnreadableError as exc:
            # The quota at one level is unknown, so the most-restrictive-level-wins
            # computation cannot be trusted; reporting host capacity here would risk
            # overstating the allocation rather than the safe direction, unknown.
            log.warning(
                "Cgroup CPU limit file %s exists but could not be read; reporting the CPU quota as unknown (host=%s)",
                exc.path,
                identity.host,
            )
            processor_assigned = None
            processor_available = None

        try:
            memory_limit, memory_current_path = _read_cgroup_memory_limit(identity.cgroup_dirs)
            memory_total = memory_limit if memory_limit is not None else _host_memory_total()
            memory_available = self._read_memory_available(
                memory_limit=memory_limit, memory_current_path=memory_current_path
            )
        except _CgroupLimitUnreadableError as exc:
            log.warning(
                "Cgroup memory limit file %s exists but could not be read; reporting memory as unknown (host=%s)",
                exc.path,
                identity.host,
            )
            memory_limit = None
            memory_total = None
            memory_available = None

        return _DynamicResources(
            processor_available=processor_available,
            processor_assigned=processor_assigned,
            memory_total=memory_total,
            memory_limit=memory_limit,
            memory_available=memory_available,
        )

    @staticmethod
    def _build_reading(identity: _ProcessIdentity, dynamic: _DynamicResources) -> WorkerResourceReading:
        return WorkerResourceReading(
            host=identity.host,
            processor_available=dynamic.processor_available,
            processor_assigned=dynamic.processor_assigned,
            memory_total=dynamic.memory_total,
            memory_available=dynamic.memory_available,
        )

    def read(self) -> WorkerResourceReading:
        identity = self._process_identity()
        return self._build_reading(identity, self._read_dynamic(identity))

    def diagnose(self) -> ResourceDiagnostics:
        """Return a reading alongside the cgroup evidence behind it."""
        identity = self._process_identity()
        cgroup_dirs = identity.cgroup_dirs
        levels = [
            CgroupLevel(
                path=str(directory),
                files={
                    name: content
                    for name in _V2_EVIDENCE_FILES
                    if (content := _read_text_file(directory / name)) is not None
                },
            )
            for directory in cgroup_dirs
        ]
        root = cgroup_dirs[-1]
        v1_files = {
            name: content for name in _V1_EVIDENCE_FILES if (content := _read_text_file(root / name)) is not None
        }
        if v1_files:
            levels.append(CgroupLevel(path=f"{root} (v1 controllers)", files=v1_files))

        dynamic = self._read_dynamic(identity)
        return ResourceDiagnostics(
            reading=self._build_reading(identity, dynamic),
            proc_cgroup=_read_text_file(self._proc_cgroup),
            cgroup_v2_root=(self._cgroup_root / "cgroup.controllers").exists(),
            cgroup_v1_root=(self._cgroup_root / "cpu" / "cpu.cfs_quota_us").exists(),
            memory_limit=dynamic.memory_limit,
            levels=levels,
            host_processor_available=identity.host_processor_count,
            host_memory_total=_host_memory_total(),
        )


def _sum_all_or_none(values: list[int | None]) -> int | None:
    """Sum the per-host values for one field, or ``None`` when it cannot be summed.

    Used only for ``processor_assigned``, where a contributing host's ``None``
    is a real value (no quota enforced), not a gap: one unbounded host means
    the fleet has no finite assignment, so it nulls the whole aggregate rather
    than being summed as zero. No values at all collapses to ``None`` too.
    """
    if not values or any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _sum_reporters(values: list[int | None]) -> int | None:
    """Sum whatever hosts reported a value for one field, or ``None`` if none did.

    Here a ``None`` from a contributing host is never a legitimate value —
    unlike an unbounded ``processor_assigned`` — so it can only be a read that
    failed for that one field. The fleet total is still finite, so the field
    is undercounted rather than nulled.
    """
    reported = [value for value in values if value is not None]
    if not reported:
        return None
    return sum(reported)


def aggregate(readings: Iterable[WorkerResourceReading]) -> ResourceAggregate:
    """Collapse per-process readings into one figure per field for a component.

    Readings are deduplicated by host (processes on one host report identical
    values). A host whose read failed outright (every figure ``None``) is
    skipped, and a host that never reported is simply absent, so both undercount
    the sum — a gap the separately-tracked worker count exposes — rather than
    nulling the whole fleet. The same holds for a host that reported only some
    fields; ``processor_assigned`` is the one exception, since a ``None`` there
    is itself a real reading rather than a gap.
    """
    by_host: dict[str, WorkerResourceReading] = {}
    for reading in readings:
        if reading.is_failed:
            continue
        by_host.setdefault(reading.host, reading)

    deduped = list(by_host.values())
    return ResourceAggregate(
        processor_available=_sum_reporters([reading.processor_available for reading in deduped]),
        processor_assigned=_sum_all_or_none([reading.processor_assigned for reading in deduped]),
        memory_total=_sum_reporters([reading.memory_total for reading in deduped]),
        memory_available=_sum_reporters([reading.memory_available for reading in deduped]),
    )
